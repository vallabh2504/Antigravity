# S V V Sai Sri Vallabh Pataneni
**Research Associate / PhD Candidate: Fuel Cell Systems (PEM & SOFC), Modeling, Simulation and Control**
Aachen, Germany · vallabh.pataneni@rwth-aachen.de · +49 176 8594 4047 · linkedin.com/in/vallabh-pataneni

## Summary
Automotive Engineering Master's student at RWTH Aachen, specialising in the modeling, simulation, and control of PEM fuel cell systems. At DLR he built the cathode-side control architecture for the ~150-200 kW EnginePod aircraft powertrain. Onto a 0D MATLAB/Simulink plant model he layered feed-forward, PI, decoupler, and a full Model Predictive Control (MPC) approach, now tuned against real measurement data. That control work rests on hands-on test-bench experience: at Ecogenium e.V., his energy-management strategy raised on-track fuel efficiency by roughly 80% and helped secure a runner-up finish at Shell Eco-Marathon 2025, on Germany's only student-built hydrogen fuel cell vehicle. Alongside this he developed FCEV operating strategies at Robert Bosch GmbH and co-authored a rule-based FCEV control paper, now in review at SAE. He is applying to RWTH's Chair of Thermodynamics of Mobile Energy Conversion Systems (TME) to advance PEM and SOFC fuel cell system modeling, control, and test-bench validation.

## Experience

### Werkstudent, Fuel Cell Systems (Aircraft) | DLR Institute for Small Aircraft Technologies (INK) · 01/2026 – Present
*Würselen (Aachen), Germany*
- **Cathode-Side Control Architecture:** Built a 0D lumped-parameter plant model of the cathode loop in MATLAB/Simulink for DLR's EnginePod, the hydrogen-electric powertrain (~150-200 kW stack) for the D-LIGHT 9-seat commuter aircraft, then designed feed-forward, PI, and decoupler control with back-pressure-valve (BPV) protection on top.
- **Model Predictive Control:** Developed a full MPC approach for the same cathode-side architecture, now tuning both the classical and MPC strategies against real system measurement data.
- **Higher-Fidelity Modeling:** Prototyping a complementary 1D lumped-parameter model of the cathode system in GT Suite, a higher-fidelity companion to the MATLAB/Simulink work for cross-checking control behaviour.
- **Balance-of-Plant Sizing:** Wrote Python- and Excel-based sizing tools to select balance-of-plant components, deriving the design specifications for the cathode, thermal-management, and sensory systems and driving their procurement.
- **System Rig Design:** Designed the complete fuel cell system rig in CATIA V5, covering packaging, piping, testing, and component orientation, optimised for easy transfer and integration.

### Operating Strategy / System Simulation Intern | Robert Bosch GmbH · 09/2025 – 12/2025
*Schwieberdingen, Germany*
- **Operating-Strategy Modeling:** Validated an iterative Simulink model of an existing rule-based power-split operating strategy inside the (FC)EVsim PHEV module, correlating its outputs against the original developer's reference Excel and measurement data.
- **Degradation-Safeguarding Strategy:** Engineered a new operating strategy in a MATLAB script for Strong Fuel Cell Hybrid EVs on a 100 kW-stack, 1.5 t FCEV pickup, safeguarding fuel-cell and HV-battery degradation by managing dynamic loads, thermal stress, low-voltage operation, SOC swing, and life cycles, parameterised via MAPs for different battery capacities and drive cycles.
- **Parametric Optimization:** Executed multi-variable parametric optimization with Genetic Algorithms and Gradient Descent to generate the control MAPs, targeting charge sustenance and minimal fuel consumption.
- **KPI Analysis & Publication:** Benchmarked the new strategy against Dynamic Programming (DP) and ECMS through post-processing of power-distribution, SOC-window, efficiency, and degradation KPIs, and co-authored a peer-reviewed manuscript on the rule-based FCEV control strategy, now in review at SAE.

## Student Club

### Mechanical / Suspension Team Lead & Pit Crew | Ecogenium e.V. (Shell Eco-Marathon) · 06/2024 – Present
*Aachen, Germany*
- **Fuel Cell System Ownership (this season):** Currently leading testing, integration, and fault diagnosis on the team's newly built water-cooled fuel cell system, Germany's only student-built hydrogen fuel cell vehicle, running structured campaigns across its electrical, thermal, and fluidic subsystems, with end-to-end ownership from component sizing and selection through CAN-bus communication, software, and control design.
- **Energy-Management & Cooling Control (this season):** Deployed the energy-management and cooling-system control strategy for the new water-cooled system in MATLAB/Simulink.
- **Fuel Cell Test Bench Development (2025 season):** Fabricated and electronically integrated a standalone fuel cell test bench for the prior air-cooled 1 kW stack, executing operational testing (purging, humidity cycling, short-circuiting) and polarisation-curve experiments, and mapped the stack's optimal thermal operating window.
- **Strategy Implementation (2025 season):** Architected and implemented the energy-management and fuel-cell temperature-control strategy in Simulink and Python; leveraging real-time competition data, it boosted on-track fuel efficiency by roughly 80% and was a critical factor in securing a runner-up finish at Shell Eco-Marathon 2025.

## Education

### M.Sc. Automotive Engineering | RWTH Aachen University · 09/2023 – Present
*Aachen, Germany · GPA 1.7 overall, 1.2 in core automotive courses*
Relevant modules: Fuel Cell System Technology, Alternative and Mobile Propulsion Systems, Simulation Sciences, Thermodynamics. Master's thesis planned in fuel-cell control-system design, building on the DLR EnginePod work.

### B.Tech Mechanical Engineering | Jawaharlal Nehru Technological University (JNTU) · 06/2019 – 04/2023
*Hyderabad, India · CGPA 9.05 (GPA 1.3, German scale)*

## Skills
**Fuel Cell Systems & Controls:** PEM system architecture · balance-of-plant sizing and selection · 0D/1D lumped-parameter plant modeling · feed-forward, PI, and decoupler control · Model Predictive Control (MPC) · back-pressure-valve protection · operating-strategy design · CAN communication
**Modeling & Simulation:** MATLAB/Simulink · GT Suite · Dymola (Modelica) · Genetic Algorithms · Gradient Descent · DP/ECMS benchmarking
**Test & Measurement:** single-cell and stack test benches · polarisation curves · purging, humidity cycling, short-circuiting · measurement-data evaluation · fault diagnosis
**Programming & Data:** Python (NumPy, Pandas, scikit-learn) · C/C++ · Power BI
**CAD & CAE:** CATIA V5 · Siemens NX · ANSYS (Structural, Fluent)

## Languages
English (Fluent, C1) · German (Intermediate, B1) · Telugu / Hindi (Native)

## Publications
- Co-author, peer-reviewed paper on a rule-based FCEV operating-strategy control approach (Robert Bosch GmbH), in review at SAE.
- "A Comprehensive Analysis of Two Innovative Aircraft Design Configurations," IJSED Research, published 11/2022.
