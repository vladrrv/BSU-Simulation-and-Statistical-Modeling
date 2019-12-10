import random
import simpy

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


def mean(l):
    if isinstance(l[0], tuple):
        return sum([x[0]*x[1] for x in l]) / sum([x[1] for x in l])
    else:
        return sum(l)/len(l)


class Simulation:
    def __init__(self, m=1, mu1=0.5, s1=0.1, t1=0.2, t2=0.5, mu2=20, s2=2, l=4/3):
        self.job_distr = lambda: random.expovariate(1 / m)
        self.proc_distr = lambda: random.normalvariate(mu1, s1)
        self.prep_distr = lambda: random.uniform(t1, t2)
        self.break_distr = lambda: random.normalvariate(mu2, s2)
        self.repair_distr = lambda: random.expovariate(l)

        self.env = simpy.Environment()
        self.container_queue = simpy.Container(self.env)

        self.queue = []
        self.queue_times = []
        self.queue_sizes = []
        self.size_start_time = 0
        self.empty_times = []
        self.empty_start_time = 0
        self.busy = False

        self.total_times = {
            "free": [],
            "prep": [],
            "working": [],
            "repair": []
        }

        self.parts_need = 0
        self.parts_made = 0

        self.env.process(self.new_part())
        self.env.process(self.break_machine())
        self.process = self.env.process(self.working())

    def new_part(self):
        self.empty_start_time = self.env.now
        self.size_start_time = self.env.now
        while True:
            job_time = self.job_distr()
            yield self.env.timeout(job_time)
            now = self.env.now
            self.parts_need += 1

            queue_size = self.container_queue.level
            self.queue_sizes.append((queue_size, now - self.size_start_time))
            self.size_start_time = now

            if queue_size == 0:
                self.empty_times.append(now - self.empty_start_time)

            self.queue.append(now)
            yield self.container_queue.put(1)

    def working(self):
        end = self.env.now  # time since last part was finished
        while True:
            yield self.container_queue.get(1)
            now = self.env.now

            queue_size = self.container_queue.level
            self.queue_sizes.append((queue_size+1, now - self.size_start_time))
            self.size_start_time = now

            if queue_size == 0:
                self.empty_start_time = now
            self.queue_times.append(now - self.queue[0])
            self.queue = self.queue[1:]

            self.total_times["free"].append(now - end)

            # Prepare for working on the part
            prep_time = self.prep_distr()
            yield self.env.timeout(prep_time)
            self.total_times["prep"].append(prep_time)

            # Start working on the part
            proc_time_left = self.proc_distr()
            self.total_times["working"].append(proc_time_left)
            while proc_time_left:
                self.busy = True
                start = self.env.now
                try:
                    yield self.env.timeout(proc_time_left)
                    # Finish working on the part
                    proc_time_left = 0

                except simpy.Interrupt:
                    # Machine breaks
                    self.busy = False
                    proc_time_left -= self.env.now - start  # time left to complete part

                    # Repair
                    for _ in range(3):
                        time_to_repair = self.repair_distr()
                        yield self.env.timeout(time_to_repair)
                        self.queue_times[-1] += time_to_repair
                        self.total_times["repair"].append(time_to_repair)

            # Part is done
            end = self.env.now
            self.busy = False
            self.parts_made += 1

    def break_machine(self):
        while True:
            yield self.env.timeout(self.break_distr())
            if self.busy:  # Only break the machine if it is currently working (???)
                self.process.interrupt()

    def run(self, T=500):
        self.env.run(until=T)

        time_str = "{:.3f} hrs"

        for key, value in self.total_times.items():
            print(f'Total {key} time:', time_str.format(sum(value)))

        print('Average working time:', time_str.format(mean(self.total_times["working"])))

        print('Free time/working time ratio: '
              f'{round(sum(self.total_times["free"])*100/sum(self.total_times["working"]), 1)}%')

        print('Waiting time in queue:',
              '\n average:', time_str.format(mean(self.queue_times)),
              '\n maximum:', time_str.format(max(self.queue_times)))

        print('Queue size:',
              '\n average:', round(mean(self.queue_sizes), 3),
              '\n maximum:', max([x[0] for x in self.queue_sizes]))

        print(f'Average empty queue time:', time_str.format(mean(self.empty_times)))

        print('Parts need:', self.parts_need)
        print('Parts made:', self.parts_made)


if __name__ == "__main__":
    simulation = Simulation()
    simulation.run()
