#!/usr/bin/env python3
"""Build two highly tailored, photo-headed, ATS-friendly resume PDFs for Vallabh.

Career-day handouts:
  1) Forschungszentrum Juelich  -> pure fuel-cell-system engineer
  2) Goldwind Global Graduate Program 2026 -> control strategy engineer

Content is drawn ONLY from his real master_resume / source resumes. House style:
zero em-dashes; en-dash only inside date ranges; his bold-lead-in bullet voice.
Single-column body = ATS-safe; photo header = German-market friendly.
Run:  python3 Resume/build_resumes.py   (from the "Job automation" folder)
"""
from __future__ import annotations
import base64, html, pathlib

HERE = pathlib.Path(__file__).resolve().parent
PHOTO = HERE / "profile_photo.jpg"
PHOTO_B64 = base64.b64encode(PHOTO.read_bytes()).decode()

CONTACT = {
    "email": "vallabh.pataneni@rwth-aachen.de",
    "phone": "+49 176 8594 4047",
    "linkedin": "linkedin.com/in/vallabh-pataneni",
    "location": "Renningen / Stuttgart, Germany",
}

# --------------------------------------------------------------------------- #
#  HTML template (one accent colour per resume; print-ready A4).               #
# --------------------------------------------------------------------------- #
def page(name, role, accent, accent_soft, summary, experience, skills,
         education, extras, languages) -> str:
    def chips(items):
        return "".join(f"<span>{html.escape(s)}</span>" for s in items)

    def sklist(items):
        return " <span class='dot'>·</span> ".join(html.escape(s) for s in items)

    def exp_block(j):
        bullets = "".join(
            f"<li><b>{html.escape(b[0])}:</b> {html.escape(b[1])}</li>" if isinstance(b, tuple)
            else f"<li>{html.escape(b)}</li>" for b in j["bullets"])
        return f"""
        <div class="job">
          <div class="top"><span class="title">{html.escape(j['role'])}</span>
            <span class="dates">{html.escape(j['dates'])}</span></div>
          <div class="sub"><span class="org">{html.escape(j['org'])}</span>
            <span class="loc">{html.escape(j['loc'])}</span></div>
          <ul>{bullets}</ul>
        </div>"""

    def edu_block(e):
        extra = f"<div class='edu-note'>{html.escape(e['note'])}</div>" if e.get("note") else ""
        return f"""
        <div class="edu">
          <div class="top"><span class="title">{html.escape(e['degree'])}</span>
            <span class="dates">{html.escape(e['dates'])}</span></div>
          <div class="sub"><span class="org">{html.escape(e['school'])}</span>
            <span class="loc">{html.escape(e['grade'])}</span></div>
          {extra}
        </div>"""

    skills_html = "".join(
        f"<div class='skrow'><span class='skcat'>{html.escape(cat)}</span>"
        f"<span class='sklist'>{sklist(items)}</span></div>" for cat, items in skills)

    extras_html = ""
    if extras:
        items = "".join(f"<li>{html.escape(x)}</li>" for x in extras["items"])
        extras_html = f"<h2>{html.escape(extras['title'])}</h2><ul class='plain'>{items}</ul>"

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{html.escape(name)} - Resume</title>
<style>
  :root{{--accent:{accent};--soft:{accent_soft};--ink:#1c2127;--muted:#5b6470;--line:#e4e7ec;}}
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0}}
  body{{font-family:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink);line-height:1.3;font-size:9.5px;}}
  .sheet{{max-width:820px;margin:0 auto;padding:20px 40px 14px;}}
  /* header */
  header{{display:flex;align-items:center;gap:20px;border-bottom:3px solid var(--accent);
    padding-bottom:11px;margin-bottom:2px;}}
  .photo{{width:96px;height:96px;border-radius:50%;object-fit:cover;flex:0 0 auto;
    border:3px solid var(--accent);box-shadow:0 0 0 3px var(--soft);}}
  .head-text{{flex:1}}
  h1{{font-size:25px;margin:0;letter-spacing:.4px;color:var(--ink);font-weight:700;text-transform:uppercase}}
  .role{{color:var(--accent);font-weight:600;font-size:13px;margin:3px 0 7px}}
  .contact{{color:var(--muted);font-size:9.6px;line-height:1.7}}
  .contact b{{color:var(--ink);font-weight:600}}
  .contact .sep{{color:var(--accent);margin:0 7px;font-weight:700}}
  /* sections */
  h2{{font-size:10.3px;text-transform:uppercase;letter-spacing:1.8px;color:var(--accent);
    border-bottom:1.5px solid var(--line);padding-bottom:2px;margin:8px 0 4px;font-weight:700}}
  p.summary{{margin:5px 0 2px;text-align:justify}}
  /* experience / education rows */
  .job,.edu{{margin:0 0 5px}}
  .top{{display:flex;justify-content:space-between;align-items:baseline}}
  .title{{font-weight:700;font-size:11px;color:var(--ink)}}
  .dates{{color:var(--muted);font-size:9.3px;white-space:nowrap;font-weight:600}}
  .sub{{display:flex;justify-content:space-between;align-items:baseline;margin:1px 0 3px}}
  .org{{color:var(--accent);font-weight:600;font-size:10px;font-style:italic}}
  .loc{{color:var(--muted);font-size:9.3px}}
  ul{{margin:2px 0 0;padding-left:15px}}
  li{{margin:1.8px 0}}
  ul.plain{{padding-left:15px}}
  .edu-note{{color:var(--muted);font-size:9.3px;margin-top:1px}}
  /* skills: clean inline rows, not bubbles */
  .skills-wrap{{margin-top:2px}}
  .skrow{{display:flex;gap:12px;align-items:baseline;padding:3px 0;border-bottom:1px solid #f1f3f5}}
  .skrow:last-child{{border-bottom:none}}
  .skcat{{flex:0 0 150px;font-weight:700;color:var(--accent);font-size:9.4px;
    text-transform:uppercase;letter-spacing:.3px}}
  .sklist{{flex:1;color:var(--ink);font-size:9.6px;line-height:1.45}}
  .sklist .dot{{color:var(--accent);font-weight:700;margin:0 2px}}
  @page{{size:A4;margin:0}}
  @media print{{.sheet{{max-width:none;margin:0;padding:26px 40px}} a{{color:inherit}}}}
</style></head><body><div class="sheet">
  <header>
    <img class="photo" src="data:image/jpeg;base64,{PHOTO_B64}" alt="photo">
    <div class="head-text">
      <h1>{html.escape(name)}</h1>
      <div class="role">{html.escape(role)}</div>
      <div class="contact">
        <b>Email</b> {html.escape(CONTACT['email'])}<span class="sep">|</span>
        <b>Phone</b> {html.escape(CONTACT['phone'])}<br>
        <b>LinkedIn</b> {html.escape(CONTACT['linkedin'])}<span class="sep">|</span>
        <b>Location</b> {html.escape(CONTACT['location'])}
      </div>
    </div>
  </header>

  <h2>Profile</h2>
  <p class="summary">{html.escape(summary)}</p>

  <h2>Professional Experience</h2>
  {''.join(exp_block(j) for j in experience)}

  <h2>Key Skills</h2>
  <div class="skills-wrap">{skills_html}</div>

  <h2>Education</h2>
  {''.join(edu_block(e) for e in education)}

  {extras_html}

  <h2>Languages</h2>
  <p class="summary" style="margin-top:4px">{html.escape(languages)}</p>
</div></body></html>"""


# --------------------------------------------------------------------------- #
#  RESUME 1 — Forschungszentrum Juelich (pure fuel-cell systems)              #
# --------------------------------------------------------------------------- #
juelich = dict(
    name="S V V Sai Sri Vallabh Pataneni",
    role="Fuel Cell System Engineer  ·  Hydrogen & Fuel Cell R&D",
    accent="#0b6e4f", accent_soft="#eaf4ef",
    summary=(
        "My path into fuel cell systems began hands-on at Ecogenium e.V., where I fabricated a "
        "standalone test bench, ran an air-cooled PEM stack through its operating window, and wrote "
        "the energy-management and thermal-control strategies that carried Germany's only "
        "student-built hydrogen car to a runner-up finish at Shell Eco-Marathon 2025. That "
        "experimental grounding took me to Robert Bosch GmbH at system level, engineering FCEV "
        "operating strategies and studying fuel-cell degradation, and then to DLR, where I am now "
        "developing a complete ~150 kW fuel cell system for a hydrogen aircraft, from a "
        "thermal-management digital twin and component sizing to the control software itself. I want "
        "to bring this full-stack experience, from stack to system to control, to the hydrogen and "
        "fuel cell research at Forschungszentrum Juelich."
    ),
    experience=[
        dict(role="Werkstudent, Fuel Cell Systems (Aircraft)",
             org="DLR, Innovation Center for Small Aircraft Technologies (INK)",
             loc="Wuerselen (Aachen), Germany", dates="01/2026 – Present",
             bullets=[
                ("Fuel Cell System Development",
                 "Developing the complete ~150 kW fuel cell system (the engine) for D-LIGHT, DLR's hydrogen-powered 9-seater feeder aircraft, from concept toward a flight-representative system."),
                ("Thermal-Management Digital Twin",
                 "Built a MATLAB/Simulink digital twin of the full thermal management system to derive design specifications (volumetric flow, coolant temperature range, coolant pressure), driving procurement of the coolant pump and heat exchanger."),
                ("Sizing & Component Selection",
                 "Selected all thermal-management components against the derived specifications and sized the subsystem for the aircraft duty cycle."),
                ("System Rig Design",
                 "Iteratively designed a compact, aircraft-engine-sized fuel cell system rig in CATIA V5, optimised for easy transferability and integration."),
                ("Upcoming Master's Thesis",
                 "Developing the fuel cell system control (start-up, purge control, cathode and anode subsystem control, temperature control, safety protocols) in MATLAB and C++ for direct deployment to the fuel cell controller."),
             ]),
        dict(role="Operating Strategy / System Simulation Intern",
             org="Robert Bosch GmbH", loc="Schwieberdingen, Germany",
             dates="09/2025 – 12/2025",
             bullets=[
                ("Energy-Management & Degradation",
                 "Engineered a MATLAB operating strategy for Strong Fuel Cell Hybrid EVs that safeguards fuel-cell and HV-battery degradation by managing dynamic loads, thermal stress, low-voltage operation, SOC swing and life cycles, parameterised via MAPs for different battery capacities and drive cycles."),
                ("Model Development & Validation",
                 "Developed and validated an iterative Simulink power-split operating-strategy model in the (FC)EVsim module, correlating outputs against reference measurement data to ensure high model fidelity."),
                ("Optimisation & Benchmarking",
                 "Executed multi-objective parametric optimisation (Genetic Algorithms, Gradient Descent) to generate control MAPs for charge sustenance and minimal fuel consumption, benchmarked against DP and ECMS; co-authoring a peer-reviewed paper on the strategy."),
             ]),
        dict(role="Fuel Cell Systems & Test-Bench Lead (Team Lead)",
             org="Ecogenium e.V (RWTH student team), Shell Eco-Marathon",
             loc="Aachen, Germany", dates="06/2024 – Present",
             bullets=[
                ("Air-Cooled Fuel Cell Test Bench",
                 "Engineered, fabricated and electronically integrated a standalone fuel cell test bench; ran purging, humidity cycling, short-circuiting and polarisation-curve experiments and mapped the stack's optimal thermal operating window."),
                ("Energy-Management & Thermal Control",
                 "Architected and deployed energy-management and fuel-cell temperature-control strategies in Python/Simulink (MIL-validated), boosting on-track fuel efficiency by ~80% and securing a runner-up finish at Shell Eco-Marathon 2025."),
                ("System Integration",
                 "Designed and tested a compact fuel cell system rig, optimising packaging density and integration of the fuel cell and its electronic systems for Germany's only student-built hydrogen fuel cell vehicle."),
             ]),
    ],
    skills=[
        ("Fuel Cell Systems", ["PEM fuel cell systems", "air-cooled stack operation", "balance of plant",
                               "thermal management", "system sizing", "component selection", "FCEV powertrain"]),
        ("Controls & Strategy", ["operating strategy", "energy management (EMS)", "degradation / SOH analysis",
                                  "MAP / lookup-table optimisation", "DP / ECMS benchmarking"]),
        ("Test & Experimentation", ["FC test-bench design", "polarisation curves", "purging / humidity cycling",
                                     "data acquisition", "model validation"]),
        ("Simulation & Modelling", ["MATLAB/Simulink (MIL)", "digital twin", "ANSYS", "Star-CCM+", "Dymola"]),
        ("Programming & Data", ["Python (NumPy, Pandas, scikit-learn)", "C/C++", "Power BI"]),
        ("CAD", ["CATIA V5", "Siemens NX", "Fusion 360"]),
    ],
    education=[
        dict(degree="M.Sc. Automotive Engineering", school="RWTH Aachen University",
             grade="GPA 1.7 (1.2 core courses)", dates="09/2023 – 06/2026",
             note="Modules: Fuel Cell System Technology, Alternative & Mobile Propulsion Systems, Thermodynamics, Simulation Sciences, FEM/CFD. Thesis: fuel cell system control (MATLAB/C++)."),
        dict(degree="B.Tech Mechanical Engineering", school="Jawaharlal Nehru Technological University, Hyderabad",
             grade="GPA 1.3 (German scale)", dates="06/2019 – 04/2023"),
    ],
    extras=dict(title="Selected Projects & Publications", items=[
        "Co-author (in preparation): rule-based FCEV powertrain control strategy, based on the Bosch internship.",
        "Electric Wheelchair with Modular Battery System (ISEA-RWTH): battery-pack architecture, cell selection, Simulink discharge/range model.",
        "Paper: A Comprehensive Analysis of Two Innovative Aircraft Design Configurations (IJSED).",
    ]),
    languages="English (C1, fluent)  ·  German (B1, intermediate)  ·  Telugu / Hindi (native)",
)

# --------------------------------------------------------------------------- #
#  RESUME 2 — Goldwind Global Graduate Program 2026 (Control Strategy)        #
# --------------------------------------------------------------------------- #
goldwind = dict(
    name="S V V Sai Sri Vallabh Pataneni",
    role="Control Strategy Engineer  ·  Global Graduate Program 2026",
    accent="#16508c", accent_soft="#eaf1f8",
    summary=(
        "My work has followed one thread: making energy systems behave the way they should through "
        "control. It started at Ecogenium e.V., where I wrote and validated real-time "
        "energy-management and temperature-control strategies in Python and Simulink that lifted our "
        "vehicle's efficiency by ~80%. At Robert Bosch GmbH I took this to industrial level, "
        "developing rule-based and predictive power-split control strategies, calibrating them with "
        "Genetic-Algorithm and Gradient-Descent optimisation, and benchmarking against Dynamic "
        "Programming and ECMS. At DLR I am now building a fuel cell system controller in MATLAB and "
        "C++ for direct deployment to hardware, with start-up, purge, subsystem and safety state "
        "logic. I am applying to Goldwind's Global Graduate Program 2026 to bring this control-strategy "
        "and model-based-development experience to your turbine control team in Frankfurt."
    ),
    experience=[
        dict(role="Operating Strategy / System Simulation Intern",
             org="Robert Bosch GmbH", loc="Schwieberdingen, Germany",
             dates="09/2025 – 12/2025",
             bullets=[
                ("Control Strategy Development",
                 "Engineered a new MATLAB control strategy for Strong Fuel Cell Hybrid EVs that manages dynamic loads, thermal stress, low-voltage operation and SOC swing, parameterised via MAPs for different operating conditions and duty cycles."),
                ("Model-Based Development & Validation",
                 "Developed and validated an iterative rule-based power-split strategy in the Simulink (FC)EVsim module, correlating simulation outputs against reference measurement data to ensure high model fidelity."),
                ("Optimisation & Benchmarking",
                 "Executed multi-objective, multi-variable parametric optimisation using Genetic Algorithms and Gradient Descent to generate control MAPs, benchmarked against Dynamic Programming and ECMS standards."),
                ("Predictive Control & Publication",
                 "Researching predictive control extensions using live GPS and road-elevation data to anticipate power demand; co-authoring a peer-reviewed paper on the control strategy."),
             ]),
        dict(role="Werkstudent, Fuel Cell System Control (Aircraft)",
             org="DLR, Innovation Center for Small Aircraft Technologies (INK)",
             loc="Wuerselen (Aachen), Germany", dates="01/2026 – Present",
             bullets=[
                ("Control-Oriented Modelling",
                 "Built a MATLAB/Simulink digital twin of the aircraft fuel cell thermal management system to derive control specifications (volumetric flow, coolant temperature range, coolant pressure) for the ~150 kW system."),
                ("Controller Development (Thesis)",
                 "Developing the fuel cell system control (start-up, purge control, cathode and anode subsystem control, temperature control, safety protocols) in MATLAB and C++ for direct deployment to the physical controller."),
                ("System Integration",
                 "Selecting subsystem components against derived specifications and designing the system rig in CATIA V5 for integration and test."),
             ]),
        dict(role="Control & Energy-Management Lead (Team Lead)",
             org="Ecogenium e.V (RWTH student team), Shell Eco-Marathon",
             loc="Aachen, Germany", dates="06/2024 – Present",
             bullets=[
                ("Real-Time Control Strategy",
                 "Architected and deployed energy-management and fuel-cell temperature-control strategies in Python/Simulink, validated with Model-in-the-Loop simulation, boosting on-track efficiency by ~80% and securing a runner-up finish at Shell Eco-Marathon 2025."),
                ("Control Validation on Hardware",
                 "Engineered and programmed a standalone test bench and correlated control models against real measurement data (polarisation curves, purging, thermal sweeps) to validate strategy before deployment."),
                ("Leadership",
                 "Led a multidisciplinary team building Germany's only student-built hydrogen fuel cell vehicle from concept to competition, coordinating control, integration and on-track troubleshooting under deadlines."),
             ]),
        dict(role="Autonomous Systems Engineer (Academic Project)",
             org="Institute for Automotive Engineering (IKA), RWTH Aachen",
             loc="Aachen, Germany", dates="04/2025 – 07/2025",
             bullets=[
                ("Controller Design & Validation",
                 "Developed models and tuned PID and MPC-based controllers in MATLAB/Simulink and Python for Adaptive Cruise Control and Lane Keep Assist, validated through real-time testing on a mock vehicle and in CARLA against real-world results."),
             ]),
    ],
    skills=[
        ("Control Methods", ["PID control", "Model Predictive Control (MPC)", "rule-based control",
                             "predictive control", "feedforward / feedback control",
                             "supervisory & state-machine control", "gain scheduling", "real-time control"]),
        ("Strategy & Calibration", ["control strategy design", "operating & energy-management strategy",
                                    "control MAP / lookup-table calibration", "multi-objective optimisation",
                                    "Genetic Algorithms", "Gradient Descent", "DP / ECMS benchmarking", "KPI analysis"]),
        ("Model-Based Development", ["MATLAB/Simulink", "digital twin", "Model-in-the-Loop (MIL)",
                                     "model & measurement validation", "C++ deployment to controller", "CARLA"]),
        ("Programming & Data", ["MATLAB", "C/C++", "Python (NumPy, Pandas, scikit-learn, PyTorch)",
                                "signal processing", "Power BI"]),
        ("Tools", ["Siemens Teamcenter", "Git", "Tableau"]),
    ],
    education=[
        dict(degree="M.Sc. Automotive Engineering", school="RWTH Aachen University",
             grade="GPA 1.7 (1.2 core courses)", dates="09/2023 – 06/2026",
             note="Modules: Simulation Sciences, Mechatronics, Machine Learning / Data Science, Alternative & Mobile Propulsion Systems. Thesis: fuel cell system control (MATLAB/C++)."),
        dict(degree="B.Tech Mechanical Engineering", school="Jawaharlal Nehru Technological University, Hyderabad",
             grade="GPA 1.3 (German scale)", dates="06/2019 – 04/2023"),
    ],
    extras=dict(title="Selected Projects & Publications", items=[
        "Co-author (in preparation): rule-based powertrain control strategy with optimisation and benchmarking, based on the Bosch internship.",
        "Vehicle Sensor Data Analysis (IKA-RWTH): Python pipelines for camera/LiDAR/radar, CNN traffic-sign recognition, Power BI dashboards.",
        "Paper: A Comprehensive Analysis of Two Innovative Aircraft Design Configurations (IJSED).",
    ]),
    languages="English (C1, fluent)  ·  German (B1, intermediate)  ·  Telugu / Hindi (native)",
)

# --------------------------------------------------------------------------- #
def build(spec, stem):
    from weasyprint import HTML
    h = page(spec["name"], spec["role"], spec["accent"], spec["accent_soft"],
             spec["summary"], spec["experience"], spec["skills"],
             spec["education"], spec["extras"], spec["languages"])
    html_path = HERE / f"{stem}.html"
    pdf_path = HERE / f"{stem}.pdf"
    html_path.write_text(h, encoding="utf-8")
    HTML(string=h, base_url=str(HERE)).write_pdf(str(pdf_path))
    # em-dash guard
    bad = h.count("—") + h.replace(" – ", "").count("–")
    print(f"[ok] {stem}: html + pdf written. em/en-dash violations: {bad}")
    return html_path, pdf_path


if __name__ == "__main__":
    build(juelich, "Vallabh_Pataneni_Resume_Forschungszentrum_Juelich_Fuel_Cell_Systems")
    build(goldwind, "Vallabh_Pataneni_Resume_Goldwind_Control_Strategy_Engineer")
    print("Done.")
