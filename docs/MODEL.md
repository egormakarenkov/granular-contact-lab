# Model and interpretation

All lengths, times, forces and work are dimensionless. Grains are rigid discs in two dimensions, with floor and side walls. The intruder motion is prescribed. Its shape is a fixed circle or ellipse; there is no shape actuation.

For timestep h, positions q, previous velocities v_old, diagonal reference mass M, damping C, and body force F, solve

```
minimize_v  1/2 v^T (C + epsilon M/h) v - (F + epsilon M v_old/h)^T v
subject to g/h + Gv + partial_t(g) >= 0.
q_next = q + h v
```

Here M has grain entries `(r/.12)^2`, C = damping × M, and F is the downward prescribed mass-weighted body force. Epsilon scales inertia independently of F. Setting epsilon to zero gives an overdamped problem; positions can still evolve. Positive damping makes the velocity objective strictly convex for the stated settings. This does not establish uniqueness of the contact-force multipliers or of a global nonlinear evolution.

OSQP solves each velocity QP. A SciPy SLSQP primal fallback and nonnegative least-squares dual recovery handle certain difficult contact sets. Acceptance also checks force balance and complementarity. Positions are checked against exact all-pair disc gaps, walls, and the intruder surface at the accepted endpoint. Excessive penetration or grain displacement triggers subdivision, with a finite depth limit. This is an implemented endpoint/displacement safeguard, not a proof that every continuous-time collision is resolved or that the full nonlinear problem converges.

## Public motion family

For 0 <= t <= T:

```
Translation: x(t) = x0; y(t) = y0 - stroke × t/T
Lateral sway: x(t) = x0 + A sin(2 pi f t) sin^2(pi t/T)
              y(t) = y0 - stroke × t/T
Hold: x(t) = x0; y(t) = y0
```

The lateral envelope returns to zero at both endpoints. The intruder keeps the same axes and angle. Translation/sway comparisons share initial arrays, duration and net downward stroke. Search uses a translation baseline and a finite grid of sway amplitudes/frequencies within the stated amplitude bound. It is not a continuous optimizer, and equal endpoints do not imply equal path length, speed, acceleration, actuator complexity, or hardware cost.

## Displayed quantities

- Normal reactions are nonnegative QP multipliers. Impulse is reaction times accepted substep duration.
- The contact inspector describes the final accepted substep of a recorded frame. Work accumulates over all accepted substeps.
- Actuator work uses the imposed boundary gap-rate term and solved multipliers. Positive work accumulates positive substep work; signed work is also exported. Neither includes a hardware motor model or physical calibration.
- Colored routes select paths within the loaded-contact graph. They visualize the selected numerical solution; they do not decompose force uniquely or establish a theorem.
- Force-range LPs bound one contact reaction using nonnegative reactions and the recorded balance target, within componentwise tolerance 3e-5. Active contacts are selected by the code's status/slack tolerances. These ranges do not select compliance, friction or loading history.
- Matrix rank/SVD, gaps, loaded-contact counts and residuals are diagnostics. Equality nullity is not the full unilateral admissible-motion cone.

## Boundaries

No tangential friction, grain spin, pore fluid, general restitution, material calibration or experimental validation is supplied. The small displacement probe measures prescribed-motion resistance, not the dynamics of a freely responding intruder. No universal fluidization classifier, general convergence result, interchangeable timestep/inertia limits, or global control optimum is claimed.
