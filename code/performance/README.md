# Performance

Within [coding standards](../README.md), this document establishes the performance standard for Pentagram: how extreme speed is engineered into the codebase through mechanical sympathy and structural discipline, and how it is defended across the software lifecycle.

For external developers, the transformative speed of the compiler (and all other tooling) must be a primary differentiator of the language. Self-compiling an exceptionally fast compiler also provides visceral proof of Pentagram's [efficiency aim](../../manifesto.md).

The same high performance standard applies to internal repo tooling. This serves as an active forcing function for the core product, and it's highly beneficial for how contributors get work done.

Achieving extreme speed is essentially about managing work that computations need to perform. The fastest thing is to do nothing or do less work, and then the remaining work needs to be tackled with proper strategy and tactics.

Maintaining extreme speed is its own complex problem: it can't be done through a single benchmark or a wall-clock timer. Similar to how comprehensive software quality requires an array of techniques from unit tests to formal proofs, performance requires multiple measurement methods working together, each with their own strengths and weaknesses.

## Performance lifecycle (the evolutionary spiral)

Treating optimization as something to defer will lead to systemic performance debt, while guessing bottlenecks in advance will just waste time and make a mess. Instead, engineering for speed follows an ongoing evolutionary spiral: **design**, **observe**, and **tune**.

**Design** establishes initial ownership boundaries, data structures, and algorithms chosen for deliberate mechanical sympathy. Good design is not premature optimization; it is setting up a proactive foundation that's grounded in past empirical lessons. It chooses contiguous memory layouts over pointer indirection, accounts for data scale regimes, and avoids unconstrained allocations before a single line of code runs.

**Observe** gathers empirical evidence across real workloads. Performance cannot be managed without continuous measurement, spanning both external program execution and internal contributor loops. Observation combines ambient push feedback—such as automated pre-merge gates and build duration timers—with on-demand pull analysis through profilers, timeline traces, and hardware counters to reveal how code actually behaves against physical hardware.

**Tune** applies evidence-driven optimization when observation reveals genuine bottlenecks. High-leverage tuning rarely consists of local peephole hacks or instruction-level tricks. Real performance bottlenecks almost always require structural redesign: altering data representations, shifting ownership boundaries, reordering operations, or eliminating entire categories of work. Because effective tuning reshapes the underlying architecture, it feeds directly back into design, establishing a new performance baseline for the next cycle.

## Data distribution and hardware reality

Software does not execute in an abstract mathematical realm. Achieving extreme speed requires mechanical sympathy: understanding how the physical machine operates and how real data is structured. Designing for performance means reckoning with four physical and algorithmic realities.

**Scale regimes ($n$):** Performance decisions must match the size of the workload. At small to moderate $n$, constant factors, cache line utilization, and branch predictability dominate runtime; a flat linear scan across contiguous memory routinely beats a balanced search tree or hash table. The flip side is equally dangerous: casually using superlinear algorithms ($O(n^2)$ or higher) on unbounded or large datasets causes catastrophic scaling cliffs in production, especially when small test cases mask the problem during development. In the absence of empirical benchmarks and distribution models, initial design should establish a sensible scale regime baseline—defaulting to linear or near-linear algorithms for workloads that can scale, while keeping small-$n$ operations flat and contiguous.

**Data shape and order:** Real-world data is rarely uniform, random noise. It can exhibit structural properties like pre-sorted sequences, power-law distributions, spatial clustering, or common prefixes. Instead of algorithms that pay for generalized worst-case guarantees, high-performance code recognizes and exploits structural patterns in data, using adaptive algorithms, specialized representations, and fast paths for dominant distributions. However, specializing code for assumed distributions carries severe risks: it creates steep performance cliffs when real inputs deviate from the expected shape, multiplies maintenance burden through divergent code paths, and introduces subtle correctness hazards for unrepresented edge cases. Exploiting data shapes must remain disciplined and heavily guarded, ensuring robust fallback behaviour and preventing speculative specialization from compromising clarity.

**Branch predictability:** Modern processors depend on speculative execution pipelines to achieve high throughput. When branches are predictable, speculative execution keeps pipelines saturated at near-zero marginal cost. When branch behaviour is erratic, mispredictions cause pipeline flushes that waste dozens of clock cycles. Sorting, clustering, or partitioning data by condition transforms unpredictable branches into predictable streams, keeping execution units fed.

**Memory access and the cache hierarchy:** The primary bottleneck on modern hardware is the memory wall. An L1 cache access takes a few cycles, while fetching from main memory takes hundreds. A single cache miss can cost more time than executing dozens of arithmetic instructions. Contiguous layouts and predictable strides allow hardware prefetchers to stream data ahead of computation, whereas pointer chasing across fragmented memory causes DRAM stalls that dwarf instruction counts.

## Disciplines of work

Managing work is the core of performance engineering. Optimization fails when effort is spent driving wasteful computation faster through clever tricks. Disciplined optimization starts by questioning the work itself and proceeds through three distinct tiers:

- **Quantity of work:** The fastest computation is one that does nothing or does less. Before rearranging or accelerating work, minimize what needs to run (eliminate, reduce, bound).

- **Structure of work:** Once the volume of work is minimized, shape how and where it lives in memory and time (localize, move, specialize).

- **Execution of work:** Finally, coordinate how the physical machine processes the remaining, well-structured work (schedule, overlap, parallelize, vectorize).

### Eliminate work (quantity)

- **Change:** Avoid executing computations whose results are unneeded, redundant, or already determined. This is an application of [subtractive design](../../rm/README.md).

- **Benefit:** Zero machine resource consumption; unexecuted work takes zero instructions, zero allocations, and zero cache space.

- **Risk:** The proof that the work is unnecessary might contain a bug, or expressing the proof in code adds complex or costly conditional logic.

### Reduce work (quantity)

- **Change:** Lower the operational cost, algorithmic complexity, or memory footprint of necessary work (such as replacing a quadratic algorithm with a linear one, or using dense integer IDs instead of heap-allocated text).

- **Benefit:** Direct, compounding throughput gains and reduced memory pressure as data volume scales.

- **Risk:** Lower-complexity algorithms and compact representations can be harder to implement, less maintainable, and carry higher constant-factor overhead on small inputs.

### Bound work (quantity)

- **Change:** Enforce explicit upper limits on worst-case resource consumption, such as maximum recursion depth, queue capacities, or execution timeouts.

- **Benefit:** Guaranteed operational stability, preventing runaway operations from exhausting memory or causing catastrophic latency spikes.

- **Risk:** The system must implement explicit policies for rejection, shedding, or backpressure when bounds are reached, accepting bounded service over uncontrolled failure.

### Localize work (structure)

- **Change:** Pack data contiguously in memory to match CPU cache lines and predictable access strides, separating frequently accessed hot fields from cold metadata. This is the primary aim of Data-Oriented Design (DOD).

- **Benefit:** Overcomes the memory wall by keeping execution pipelines saturated from L1 and L2 caches rather than stalling on DRAM. Also, thoughtful memory layout is often unlocked by thoughtful data transformation design.

- **Risk:** Packed layouts make structural mutations expensive, and their complexity can make them less maintainable.

### Move work (structure)

- **Change:** Relocate computation across time boundaries (precomputing values or amortizing costs) or resource ownership boundaries (shifting work between client and server, CPU and GPU, or application memory and disk).

- **Benefit:** Places processing where resources are best suited—leveraging specialized hardware, data proximity, or idle capacity while slashing serialization and transfer overhead across buses and networks.

- **Risk:** Crossing temporal or resource boundaries introduces transfer latency and staleness, requires coordination protocols, and creates tight coupling between execution phases or system layers.

### Specialize work (structure)

- **Change:** Replace general-purpose abstractions with dedicated execution paths tuned to dominant types, static configurations, or known data shapes.

- **Benefit:** Maximal efficiency and zero abstraction penalty, eliminating branch overhead and dynamic dispatch for the common case.

- **Risk:** Inputs deviating from the specialized path suffer steep performance cliffs, while duplicate logic across fast and general paths multiplies maintenance burden and invites correctness bugs.

### Schedule work (execution)

- **Change:** Reorder execution by batching similar tasks together, prioritizing the latency-critical path, and deferring background maintenance.

- **Benefit:** Higher throughput and cache reuse by amortizing initialization costs and eliminating frequent context switches and cache thrashing.

- **Risk:** Batching introduces queuing delay for early items while awaiting a full batch, trading individual turnaround latency for aggregate efficiency.

### Overlap work (execution)

- **Change:** Structure execution as an asynchronous pipeline so computation advances while independent operations wait on storage, networking, or peripheral devices.

- **Benefit:** Converts idle waiting time into productive work, effectively hiding the latency of slow external operations.

- **Risk:** Increases system complexity through asynchronous state management, inter-stage buffer coordination, and more complicated error recovery when in-flight operations fail.

### Parallelize work (execution)

- **Change:** Divide independent computations across multiple processor cores to execute concurrently, relying on pure transformations over immutable data.

- **Benefit:** Scales computational throughput linearly with available hardware cores for data-independent workloads without locking or data races.

- **Risk:** Thread dispatch and data coordination carry overhead; if work units are too fine-grained, coordination costs exceed execution time, running slower than sequential code.

### Vectorize work (execution)

- **Change:** Restructure computation and data layouts so SIMD hardware instructions operate on multiple packed values simultaneously rather than one at a time. Adopting a branch-free design—pushing conditional decisions into data representations and arithmetic—unlocks vectorization across domains conventionally treated as branch-bound.

- **Benefit:** Multiplies computational throughput per clock cycle by utilizing wide hardware execution units on a single core, while branch-free data flows also eliminate pipeline stalls and branch mispredictions.

- **Risk:** Increases implementation complexity through compound operations, scalar fallbacks, portability concerns, and boundary handling for loop tails. If data requires non-contiguous memory access or inputs are small, vectorization overhead can exceed scalar execution.

## Modes of measurement

No single measurement mode catches every performance defect. Statistical benchmarks cannot anticipate unrepresented production workloads and can mask algorithmic defects that amplify only under scale. Conversely, production telemetry is too noisy for regression gating, and instruction-level simulation is too slow for interactive feedback loops.

Comprehensive performance coverage requires a complementary measurement mesh that spans four canonical lifecycle stages:

- **`dev loop`:** The local environment where contributors write and test code. It demands immediate, sub-second feedback to guide design decisions without disrupting contributor flow.

- **`pre-merge`:** The automated integration gate that validates pull requests. It requires fast, noise-free verification to block regressions without false alarms or flaky failures.

- **`post-merge`:** Asynchronous verification pipelines running on dedicated hardware. It accommodates compute-intensive benchmarks, hardware counters, and deep simulations that are too slow for pre-merge gates.

- **`field`:** Live production deployments executing on diverse client environments. It observes unconstrained workloads, real data distributions, and tail latencies to uncover unexpected bottlenecks and feed the next design cycle.

Each measurement mode targets a distinct layer of execution, carrying specific strengths and trade-offs that determine where it fits within these four stages.

### Deterministic cost accounting

- **Target:** It measures invariant execution counts that remain identical across identical runs, tracking retired instructions, heap allocations, allocated bytes, and loop or traversal iterations.

- **Strengths:** Cost accounting is completely deterministic and immune to host environment noise. It provides a reliable regression gate that detects regressions immediately without producing false alarms or flaky CI failures.

- **Weaknesses:** Work counters are disconnected from physical silicon realities, remaining blind to cache misses, pipeline stalls, branch mispredictions, and memory bus latency. Reducing the number of retired instructions or allocations does not guarantee faster elapsed time on real hardware.

- **Ideal stages:** This mode is best suited for the `dev loop` and `pre-merge` CI gates because its noise-free determinism guarantees that tests never flake or block contributors with false regressions.

### Wall-clock latency timers

- **Target:** It measures total elapsed physical duration for high-level operations, capturing command-line invocations, batch transformations, network requests, and frame render intervals.

- **Strengths:** Wall-clock timers directly measure the perceptible latency experienced by developers and callers. They are straightforward to instrument and provide natural ambient feedback in local workflows and command logs.

- **Weaknesses:** Elapsed physical time provides coarse aggregate measurements with no internal attribution. It is highly susceptible to host machine noise, operating system scheduling, background processes, and thermal throttling, making it too noisy for automated gating.

- **Ideal stages:** Timers are essential in the `dev loop` for immediate developer feedback and in the `field` to monitor end-to-end operation durations across production deployments.

### Timeline traces and spans

- **Target:** It records causal event timelines, scheduling intervals, thread dependencies, and concurrency overlap between computation and external I/O.

- **Strengths:** Traces reveal concurrency bottlenecks, thread contention, idle scheduling gaps, and pipeline stalls. They provide an exact structural explanation for single-run latency spikes and asynchronous delays.

- **Weaknesses:** Tracing generates substantial data volume and requires purposeful instrumentation boundaries. It captures individual execution instances rather than aggregate statistical distributions, requiring targeted reproduction to analyze issues.

- **Ideal stages:** Tracing is ideal in the `dev loop` for diagnosing specific concurrency bugs and in the `field` to capture diagnostic traces of pathological production requests.

### Statistical sampling profiling

- **Target:** It periodically samples call stacks on unmodified production binaries to construct execution time and memory allocation profiles.

- **Strengths:** Low runtime overhead, typically between one and three percent, allows profilers to run continuously in production and local developer loops. Sampling quickly identifies hot execution paths and areas of excessive allocation churn without distorting application behaviour.

- **Weaknesses:** Sampling produces statistical approximations rather than exact event counts, leaving it vulnerable to sampling bias during short-lived bursts. It also remains blind to off-CPU wait time and thread sleep states without specialized kernel instrumentation.

- **Ideal stages:** Profiling is well suited for interactive profiling in the `dev loop` and continuous fleet monitoring in the `field`.

### Dynamic binary instrumentation

- **Target:** It simulates processor execution at the machine-instruction level, tracking cache hierarchy misses, detailed call graphs, and heap memory lifetimes.

- **Strengths:** Instrumentation provides comprehensive, noise-free attribution down to individual lines of code and branch decisions. It pinpoints structural cache misses and memory layout inefficiencies without host machine jitter.

- **Weaknesses:** Full binary simulation introduces extreme slowdowns, typically running ten to fifty times slower than native execution. In addition, synthetic cache and branch models are idealized approximations that can diverge from the behaviour of physical silicon.

- **Ideal stages:** This mode belongs in `post-merge` analysis pipelines and on-demand local deep dives within the `dev loop`, where its heavy computational cost does not stall fast integration cycles.

### Hardware performance counters

- **Target:** It queries physical processor execution events directly from silicon registers, tracking instructions per cycle, cache hit ratios, branch mispredictions, memory bus saturation, and accelerator execution unit occupancy.

- **Strengths:** Performance counters expose true mechanical sympathy with the target silicon, uncovering microarchitectural bottlenecks that instruction counters and high-level timers miss. On accelerators, occupancy metrics and pipeline stall counters provide an exhaustive view of kernel efficiency.

- **Weaknesses:** Performance counters are vendor-specific and non-portable across architectures. They require elevated operating system privileges or dedicated bare-metal test runners, and out-of-order execution pipelines introduce attribution skid that can blur which exact instruction triggered an event.

- **Ideal stages:** This mode is best suited for dedicated `post-merge` performance labs on bare-metal runners, as well as on-demand microarchitectural investigation within the `dev loop`.

### Statistical benchmark distributions

- **Target:** It evaluates complete latency distributions ($p50$, $p95$, and $p99$) alongside interior time budgets for constituent phases, derived from controlled, repeated executions on dedicated bare-metal hardware.

- **Strengths:** Controlled benchmarks measure true physical latency and tail behaviour under repeatable test conditions, establishing statistical confidence against regression thresholds. Tracking interior time budgets establishes explicit quality-of-service (QoS) levels across subsystems and immediately isolates the root cause when a latency target fails.

- **Weaknesses:** Establishing statistical confidence is expensive in execution time and hardware resources. In addition, synthetic benchmark suites can miss latent algorithmic regressions if test inputs fail to represent production scale regimes or wild data distributions.

- **Ideal stages:** This mode belongs in `post-merge` integration pipelines running on isolated, dedicated hardware to protect test stability from host noise.

### Aggregate telemetry and flight recorders

- **Target:** It captures population-wide metric distributions and circular-buffer flight recordings from live production deployments.

- **Strengths:** Telemetry exposes real-world unconstrained workloads, rare data shapes, and heterogeneous hardware environments that synthetic test suites fail to anticipate. Flight recorders preserve the causal history leading up to rare tail-latency spikes or failures.

- **Weaknesses:** Telemetry provides delayed feedback and coarse aggregate signals across diverse client environments. Data collection is strictly constrained by privacy boundaries and data confidentiality, requiring reproducible local test cases to diagnose root causes.

- **Ideal stages:** This mode operates exclusively in the `field`, providing the empirical workload distributions that feed the next design cycle.
