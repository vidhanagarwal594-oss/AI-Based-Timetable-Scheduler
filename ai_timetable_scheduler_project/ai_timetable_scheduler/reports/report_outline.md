# AI-Based Timetable Scheduler — Report Outline

Target length: 6–10 pages. Replace all prompts with your team's actual implementation and measured results.

## 1. Problem formulation
Describe variables (required teaching sessions), domains (day, start period, compatible room), fixed subject-teacher mapping, unary constraints and binary constraints.

## 2. Algorithms
Explain plain backtracking, MRV, degree heuristic, LCV ordering, forward checking, and Min-Conflicts. Document initialization, tie-breaking, random seed, restart strategy, and stopping limits.

## 3. Cost function
`Cost = 1000 × hard violations + soft penalties`. Explain each implemented soft penalty and its weight.

## 4. Experimental setup and results
Run both algorithms on both datasets. For randomized algorithms, run 10 trials and report average runtime, nodes/iterations, hard violations, soft penalty, and success rate. Include an actual cost-versus-iteration graph for Min-Conflicts.

## 5. Analysis
Discuss which method was faster on your measurements, timetable quality, scaling, failure cases, and appropriate use cases.

## 6. Limitations and future work
Discuss fixed teacher assignment, local-search failure, search time limits, richer preferences, persistence, and optional Simulated Annealing.

## 7. Team contributions
List each member's actual contribution. Do not invent contributions or experimental outcomes.
