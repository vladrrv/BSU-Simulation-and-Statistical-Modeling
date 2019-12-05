import random
import simpy

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


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
        self.busy = False

        self.free_time = 0
        self.prep_time = 0
        self.working_time = 0
        self.repair_time = 0
        self.parts_made = 0

        self.env.process(self.new_part())
        self.env.process(self.break_machine())
        self.process = self.env.process(self.working())

    def new_part(self):
        while True:
            yield self.env.timeout(self.job_distr())
            self.queue.append(self.env.now)
            yield self.container_queue.put(1)

    def working(self):
        end = self.env.now  # time since last part was finished
        while True:
            yield self.container_queue.get(1)
            self.queue_times.append(self.env.now - self.queue[0])
            self.queue = self.queue[1:]

            self.free_time += self.env.now - end

            # Prepare for working on the part
            prep_time = self.prep_distr()
            yield self.env.timeout(prep_time)
            self.prep_time += prep_time

            # Start working on the part
            proc_time_left = self.proc_distr()
            self.working_time += proc_time_left
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
                        self.repair_time += time_to_repair

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
        print(f'Total free time:\t{self.free_time:.3f} hrs')
        print(f'Total prep time:\t{self.prep_time:.3f} hrs')
        print(f'Total working time:\t{self.working_time:.3f} hrs')
        print(f'Total repair time:\t{self.repair_time:.3f} hrs')
        print('Parts made:', self.parts_made)
        print('Waiting time in queue:')
        print(f' average:\t{sum(self.queue_times)/len(self.queue_times):.3f} hrs')
        print(f' maximum:\t{max(self.queue_times):.3f} hrs')


if __name__ == "__main__":
    simulation = Simulation()
    simulation.run()
