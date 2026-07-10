# Resumes — real source resumes (voice + content reference)

Two real, previously-built resume PDFs, each a merged set of many company/role-tailored
variants (`Resume_Merged_1.pdf` = 31 pages, `Resume_Merged_2.pdf` = 23 pages). These are
the actual source material the `house-style` skill refers to (`skill/sources_resumes/` is
gitignored and wasn't present in this repo/session until now — this `Resumes/` folder is
where they live instead).

`Resume_Merged_1.txt` and `Resume_Merged_2.txt` are plain-text extractions (`pdftotext -layout`)
of the same files, kept alongside for fast searching (`grep`) instead of re-reading the PDFs.

## What's in here
- Every variant is tailored to a different target company/role (Porsche, Goldwind, Fraunhofer
  IAO, MAHLE, EKPO, ElringKlinger, and others), but all draw from the same real underlying
  experience: DLR, Robert Bosch GmbH, Ecogenium e.V., and Techolution.
- **Coverage gap**: none of these variants include the DLR Werkstudent role (they all predate
  January 2026). For DLR content, the source of truth is what Vallabh has stated directly in
  chat sessions — treat these files as authoritative for Bosch / Ecogenium / Techolution /
  education / publications / skills, and for house style/voice, but not for DLR specifics.
- Confirmed real details worth knowing about for future tailoring: Dymola (Modelica) and ANSYS
  (Fluent, Structural, ACP) appear repeatedly — useful when a JD asks for Modelica or CFD tools.
  PyTorch, scikit-learn, MSC ADAMS, Siemens Teamcenter, Fusion 360 Manage, PTC Creo, SolidWorks,
  Tableau also appear. The "Vehicle Sensor Data analysis Project (IKA-RWTH, 04/2025-07/2025)"
  is real and includes a genuine Model Predictive Control (MPC) component (trajectory
  optimization for intersection management) plus a CNN-based traffic-sign recognition system —
  separate from the DLR cathode-side MPC work.

## Contains personal data
These PDFs include phone number, home address, and date of birth. They're committed here at
Vallabh's explicit request; be mindful before reusing this content in any application that
doesn't need that level of detail (most job/PhD applications should omit DOB and home address).
