"""
Defense Procurement Classification Module - FINAL VERSION
==========================================================
Classification Logic:
- CRITICAL: Procurement ITEM matches future-warfare/intelligence SYSTEMS
- ROUTINE: Everything else (default)

Unit/Organization keywords are extracted as METADATA only - they do NOT
affect classification. A cleaning contract for DRDO is still ROUTINE.

Version: 4.0 FINAL
"""

import re
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict


# =============================================================================
# NAMED INDIAN SYSTEMS (Instant CRITICAL - Confidence 1.0)
# =============================================================================

NAMED_SYSTEMS = {
    # Electronic Warfare Systems
    "Samyukta", "Himshakti", "Shakti", "Sangraha", "Divya Drishti",
    "Porpoise", "Tempest", "GBMES", "Tarang", "DJAG", "Ajanta",
    
    # Radars & Surveillance
    "Ashwini", "Arudhra", "Revathi", "RAWL-02", "RAWL-03",
    "BFSR-SR", "BFSR-MR", "BFSR-LR", "CSR", "BOSS", "BELROS",
    "Netra", "AEELS", "AISIS", "Aslesha", "Rohini", "Rajendra",
    "Indra", "3D-CAR", "Akashteer", "Bharani",
    
    # Anti-Drone/C-UAS
    "NADS", "D4 System", "IDDIS",
    
    # Air Defence Systems
    "Akash", "Akash-NG", "Akash Prime", "QRSAM", "MRSAM", "LRSAM",
    "Barak", "S-400", "SAMAR", "Trishul", "Anant Shastra",
    
    # Missiles & Strike
    "BrahMos", "Nirbhay", "Shaurya", "Pralay", "Prahaar", "Pinaka",
    "Agni", "Prithvi", "Nag", "HELINA", "SANT", "Rudram", "Astra",
    "VL-SRSAM", "SMART",
    
    # UAV/Drones
    "Rustom", "Tapas", "CATS", "Ghatak", "SWiFT", "Archer",
    "Lakshya", "ABHYAS", "Nishant", "Muntra", "DRDO Netra",
    
    # Naval Systems
    "Varunastra", "Shyena", "USHUS", "HUMSA", "Maareech", "Kavach",
    "Sanket", "Nagan", "Abhay", "ACTCM", "Mareech",
    
    # Night Vision/Optronics
    "CORAL", "Netro", "Bharat", "Drishti",
    
    # Networks/C4ISR
    "AREN", "ASCON", "NC3I", "NMDA", "AFNET", "IACCS", "CIDSS",
    
    # Space Systems
    "GSAT", "IRNSS", "NavIC", "Cartosat", "RISAT", "EMISAT", "TES",
    "Oceansat", "Resourcesat",
}


# =============================================================================
# CRITICAL ITEM KEYWORDS - THESE DETERMINE CLASSIFICATION
# =============================================================================

# Domain 1: UAS / Drones
UAS_KEYWORDS = {
    # Platforms
    "UAV", "UAS", "RPAS", "drone", "unmanned aerial", "unmanned aircraft",
    "remotely piloted", "remotely piloted aircraft",
    "MALE UAV", "MALE drone", "HALE UAV", "HALE drone",
    "tactical UAV", "tactical drone", "mini UAV", "mini drone",
    "micro UAV", "micro drone", "nano UAV", "nano drone",
    "loitering munition", "loitering drone", "kamikaze drone",
    "FPV drone", "FPV strike", "FPV strike drone",
    "swarm drone", "drone swarm", "swarm", "swarming",
    "loyal wingman", "loyal-wingman", "collaborative combat aircraft",
    "optionally manned", "optionally-manned", "optionally piloted",
    "rotary UAV", "rotary-wing UAV", "rotary-wing logistics drone",
    "VTOL UAV", "VTOL drone", "fixed wing UAV", "fixed-wing UAV",
    "quadcopter", "hexacopter", "octocopter", "multirotor", "multi-rotor",
    "one-way attack drone", "attack drone", "strike drone",
    "logistics drone", "cargo drone", "delivery drone",
    "reconnaissance UAV", "recce UAV", "surveillance UAV",
    
    # Payloads
    "EO/IR gimbal", "gimbal", "UAV payload", "drone payload",
    "drone camera", "UAV camera", "aerial camera",
    "SAR payload", "SAR radar", "GMTI", "ground moving target indicator",
    "SIGINT pod", "COMINT pod", "EW pod", "ISR pod",
    "designator pod", "targeting pod", "laser designator",
    "light precision weapon", "drone munition", "release mechanism",
    
    # Components
    "flight controller", "autopilot", "UAV autopilot", "drone autopilot",
    "drone datalink", "UAV datalink", "C2 link", "command link",
    "anti-jam GNSS", "anti-jam GPS", "jam-resistant GNSS",
    "drone propulsion", "UAV propulsion", "electric propulsion",
    "heavy-fuel engine", "drone engine", "UAV engine",
    "drone battery", "UAV battery", "fuel cell drone", "fuel cell",
    "drone airframe", "UAV airframe", "composite airframe",
    "replacement airframe",
    
    # Software/Autonomy
    "autonomy stack", "autonomy software", "autonomous flight",
    "swarm coordination", "swarm algorithm", "swarm intelligence",
    "GNSS-denied navigation", "GPS-denied navigation", "visual navigation",
    "terrain following", "terrain avoidance", "obstacle avoidance",
    "sense and avoid", "sense-and-avoid", "detect and avoid", "DAA",
    "sensor-to-shooter", "sensor to shooter",
    "waypoint navigation", "autonomous waypoint",
    
    # Ground Segment
    "ground control station", "GCS", "drone GCS", "UAV GCS",
    "portable GCS", "mobile GCS", "man-portable GCS",
    "catapult launcher", "catapult", "drone launcher", "UAV launcher",
    "recovery net", "recovery system", "drone recovery",
    "ground data terminal", "GDT", "data terminal",
    
    # Services (for critical systems)
    "drone integration", "UAV integration", "drone system integration",
    "UAV training", "drone training", "drone simulator", "UAV simulator",
    "drone-as-a-service", "ISR-as-a-service", "DaaS",
    "drone MRO", "UAV MRO",
}

# Domain 2: USV
USV_KEYWORDS = {
    # Platforms
    "USV", "unmanned surface vessel", "unmanned surface vehicle",
    "autonomous surface vessel", "autonomous surface vehicle",
    "uncrewed boat", "unmanned boat", "robotic boat",
    "autonomous patrol boat", "patrol USV",
    "mine countermeasure USV", "MCM USV", "mine-warfare USV",
    "ASW USV", "anti-submarine USV", "strike USV", "combat USV",
    "mothership", "USV mothership", "uncrewed mothership",
    "autonomous fast interceptor", "fast interceptor",
    "surface drone", "sea drone",
    
    # Payloads
    "towed sonar", "hull sonar", "hull-mounted sonar",
    "surface-search radar", "surface search radar",
    "remote weapon station", "RWS", "unmanned weapon station",
    "mine-detection payload", "mine detection",
    
    # Components
    "marine propulsion", "maritime propulsion", "waterjet",
    "sea-state-tolerant", "sea state tolerant",
    "USV SATCOM", "maritime SATCOM",
    "marine battery", "maritime battery",
    
    # Software
    "autonomous navigation", "maritime autonomous",
    "COLREGS compliance", "COLREGS", "collision avoidance maritime",
    "multi-vehicle control", "multi-USV", "fleet control",
    "behaviour library", "behavior library",
    
    # Ground/Support
    "shore control centre", "shore control", "ship control centre",
    "USV recovery", "boat recovery",
    
    # Services
    "USV integration", "sea trials", "sea trial", "maritime trials",
}

# Domain 3: UUV/XLUUV
UUV_KEYWORDS = {
    # Platforms
    "UUV", "AUV", "XLUUV", "autonomous underwater vehicle",
    "unmanned underwater vehicle", "underwater drone",
    "extra-large UUV", "large UUV", "medium UUV", "small UUV",
    "autonomous glider", "underwater glider", "ocean glider",
    "seabed crawler", "bottom crawler",
    
    # Payloads
    "side-scan sonar", "side scan sonar", "synthetic aperture sonar",
    "SAS sonar", "forward-looking sonar",
    "magnetometer", "underwater magnetometer",
    "environmental sensor", "oceanographic sensor",
    "payload bay", "modular payload",
    
    # Components
    "long-endurance battery", "underwater battery", "AIP propulsion",
    "AIP", "air-independent propulsion",
    "pressure hull", "titanium hull",
    "underwater acoustic comms", "acoustic modem", "acoustic communication",
    "underwater datalink", "subsea datalink",
    "doppler velocity log", "DVL",
    
    # Software
    "long-duration autonomy", "underwater autonomy",
    "acoustic networking", "underwater network",
    "seabed-mapping", "seabed mapping", "bathymetric",
    "terrain-aided navigation",
    
    # Ground/Support
    "docking station", "underwater docking",
    "charging station", "underwater charging",
    "sub-surface comms node", "subsea node",
    
    # Services
    "ASW sensor-net", "ASW network", "sensor net",
    "deep-water trials", "deep water trial",
    "seabed warfare", "subsea warfare",
}

# Domain 4: UGV
UGV_KEYWORDS = {
    # Platforms
    "UGV", "unmanned ground vehicle", "robotic vehicle",
    "autonomous ground vehicle", "ground robot",
    "robotic mule", "logistics robot", "cargo robot",
    "logistics UGV", "recce UGV", "combat UGV",
    "autonomous convoy", "convoy autonomy", "autonomous convoy kit",
    "optionally-crewed", "optionally crewed",
    "remote controlled vehicle", "RCV",
    "tracked UGV", "wheeled UGV",
    
    # Payloads
    "modular mission payload", "casualty-evac", "casualty evacuation",
    "UGV weapon", "remote weapon", "UGV sensor",
    
    # Components
    "drive-by-wire", "drive by wire", "steer-by-wire",
    "terrain perception", "terrain sensor",
    "LiDAR", "LIDAR", "ground LiDAR",
    "edge compute", "edge computing", "edge processor",
    
    # Software
    "manned-unmanned teaming", "manned unmanned teaming", "MUM-T",
    "autonomy middleware", "robot middleware", "ROS",
    "fleet orchestration", "multi-robot",
    "path planning", "route planning",
    
    # Ground/Support
    "robotic control node", "control node",
    "charging bay", "maintenance bay", "robot bay",
    
    # Services
    "teaming trials", "MUM-T trials",
    "autonomy certification", "robot certification",
    "robotic-logistics-as-a-service",
}

# Domain 5: Counter-UAS
COUNTER_UAS_KEYWORDS = {
    # Detection
    "counter-UAS", "counter-drone", "anti-drone", "C-UAS",
    "drone detection", "UAV detection", "small target detection",
    "drone radar", "counter-drone radar", "C-UAS radar",
    "RF detector", "drone RF detector", "RF detection",
    "direction-finder", "direction finder",
    "acoustic sensor", "acoustic detection", "drone acoustic",
    "EO/IR tracker", "electro-optic tracker", "drone tracker",
    "swarm detection", "micro drone detection",
    
    # Defeat
    "RF jammer", "drone jammer", "C-UAS jammer",
    "GNSS jammer", "GPS jammer", "navigation jammer",
    "drone spoofer", "GNSS spoofer", "GPS spoofer", "spoofer",
    "high power microwave", "high-power microwave", "HPM",
    "net capture", "drone net", "net gun", "drone catcher",
    "kinetic interceptor", "anti-drone missile", "C-UAS interceptor",
    "C-UAS laser", "drone laser", "laser defeat",
    "hard kill", "soft kill", "drone defeat",
    "drone neutralization", "drone mitigation",
    
    # Components
    "fusion processor", "sensor fusion processor",
    "low-latency datalink", "low latency datalink",
    
    # Software
    "detect-track-classify", "detect track classify",
    "detect-track-classify-defeat", "DTCD",
    "drone classification", "threat classification",
    "AI drone detection", "ML drone detection",
    "sensor fusion C-UAS", "C-UAS sensor fusion",
    "drone-vs-drone", "drone vs drone", "interceptor drone",
    
    # Infrastructure
    "fixed-site C-UAS", "fixed site C-UAS", "static C-UAS",
    "vehicle-mounted C-UAS", "mobile C-UAS",
    "C-UAS suite", "integrated C-UAS", "command node",
    
    # Services
    "C-UAS integration", "layered-defence", "layered defence",
}

# Domain 6: Air Defence
AIR_DEFENCE_KEYWORDS = {
    # Systems
    "air defence", "air defense", "AD system", "AD network",
    "SAM", "surface to air missile", "surface-to-air missile",
    "short range SAM", "short-range SAM", "SR-SAM",
    "medium range SAM", "medium-range SAM", "MR-SAM",
    "long range SAM", "long-range SAM", "LR-SAM",
    "VSHORAD", "very short range air defence",
    "SHORAD", "short range air defence",
    "MANPAD", "MANPADS", "man-portable air defence",
    "point defence", "point defense", "area defence",
    "gun system", "air defence gun", "AAA",
    "CIWS", "close-in weapon system",
    "IAMD", "integrated air missile defence",
    "ballistic missile defence", "BMD", "anti-ballistic",
    "terminal defence", "terminal defense",
    "interceptor missile", "interceptor", "anti-aircraft",
    "missile defence", "missile defense",
    
    # Components
    "fire control radar", "fire-control radar", "FCR",
    "engagement radar", "tracking radar", "AD radar",
    "seeker", "missile seeker",
    "launcher", "missile launcher", "vertical launcher", "VLS",
    "missile component", "guidance section",
    "battle-management hardware", "BMC3",
    
    # Software
    "AD battle management", "air defence battle management",
    "track correlation", "track fusion",
    "engagement decision", "decision-support",
    "threat evaluation", "weapon assignment",
    "ADOC", "air defence operations centre",
    
    # Infrastructure
    "command-and-control centre", "AD command centre",
    "sensor network", "radar network", "magazine", "missile storage",
}

# Domain 7: DEW
DEW_KEYWORDS = {
    # Systems
    "directed energy", "DEW", "directed energy weapon",
    "laser weapon", "laser weapon system", "HEL",
    "high energy laser", "high-energy laser",
    "solid state laser", "solid-state laser", "SSL",
    "fibre laser", "fiber laser",
    "high power microwave", "high-power microwave", "HPM",
    "HPM weapon", "microwave weapon",
    "beam director", "beam-director",
    "C-UAS laser", "counter-drone laser",
    "C-RAM laser", "C-RAM", "counter-rocket laser",
    
    # Components
    "laser source", "laser module", "laser gain medium",
    "beam control", "beam-control", "beam steering",
    "thermal management", "cooling system", "heat dissipation",
    "optics", "beam optics", "adaptive optics",
    "atmospheric compensation", "turbulence compensation",
    
    # Software
    "target tracking", "laser tracking",
    "beam-control software", "pointing control", "aimpoint selection",
    
    # Infrastructure
    "platform-mount", "platform mount", "vehicle mount",
    "naval mount", "ship mount", "DEW range",
    
    # Services
    "DEW prototyping", "laser prototyping",
    "lethality trials", "lethality testing",
    "DEW integration", "laser integration",
}

# Domain 8: EW/SIGINT
EW_SIGINT_KEYWORDS = {
    # Core EW
    "electronic warfare", "EW", "EW system", "EW suite",
    "electromagnetic warfare", "EMS operations",
    "electronic attack", "EA",
    "electronic protection", "EP",
    "electronic support", "ES",
    "ESM", "electronic support measures",
    "ELINT", "electronic intelligence",
    "SIGINT", "signals intelligence",
    "COMINT", "communications intelligence",
    "TELINT", "telemetry intelligence",
    "FISINT", "foreign instrumentation signals intelligence",
    "ESM receiver", "SIGINT receiver",
    "ECM", "electronic countermeasures",
    "ECCM", "electronic counter-countermeasures",
    
    # Jamming
    "jammer", "jamming system", "jamming",
    "radar jammer", "comms jammer", "communications jammer",
    "COMJAM", "communications jamming",
    "barrage jamming", "barrage jammer",
    "spot jamming", "spot jammer",
    "noise jamming", "noise jammer",
    "deceptive jamming", "deception jammer",
    "DRFM", "digital RF memory", "DRFM-based",
    "responsive jamming", "reactive jamming",
    
    # Direction Finding
    "direction finding", "direction-finding", "DF",
    "DF system", "DF array", "DF antenna",
    "radio direction finder", "RDF",
    "emitter location", "emitter geolocation",
    "geolocation RF", "RF geolocation",
    "angle of arrival", "AoA",
    "time difference of arrival", "TDoA",
    "frequency difference of arrival", "FDoA",
    "triangulation", "multilateration",
    
    # Interception
    "intercept receiver", "interception receiver",
    "interception", "signal interception",
    "radio intercept", "communications intercept",
    "spectrum monitoring", "spectrum surveillance",
    "frequency monitoring", "RF monitoring",
    "wideband receiver", "broadband receiver",
    "search receiver", "scanning receiver",
    "monitoring receiver", "surveillance receiver",
    "signal analysis", "signal processing",
    "signal classification", "signal identification",
    
    # Components
    "wideband antenna", "broadband antenna",
    "RF front-end", "RF front end", "RF frontend",
    "software-defined radio", "software defined radio", "SDR",
    "digital receiver", "channelized receiver",
    
    # Software
    "cognitive EW", "adaptive EW",
    "electromagnetic battle management", "EMBM",
    "spectrum management", "spectrum deconfliction",
    "threat library", "emitter library", "EOB",
    "radar fingerprinting", "signal fingerprinting",
    "electronic order of battle",
    
    # Decoys
    "decoy", "RF decoy", "radar decoy",
    "chaff", "chaff dispenser",
    "flare", "IR flare",
    "expendable countermeasure", "expendable",
    "towed decoy", "towed RF decoy",
    
    # Infrastructure
    "EW operations centre", "EW operations center",
    "ground SIGINT station", "SIGINT station",
    "EW range", "EW test range",
    
    # Services
    "threat-library development", "threat library development",
    "cognitive-EW research", "cognitive EW research",
    "spectrum survey", "spectrum surveys",
}

# Domain 9: Strike
STRIKE_KEYWORDS = {
    # Missiles/Munitions
    "cruise missile", "land attack cruise missile", "LACM",
    "ballistic missile", "tactical ballistic missile",
    "hypersonic", "hypersonic missile", "hypersonic weapon",
    "hypersonic glide", "hypersonic glide vehicle", "HGV",
    "hypersonic cruise", "hypersonic cruise missile",
    "loitering munition", "loitering deep-strike", "deep-strike munition",
    "precision guided munition", "precision-guided munition", "PGM",
    "smart bomb", "guided bomb", "JDAM",
    "precision strike", "deep strike", "long range strike",
    "standoff weapon", "standoff munition",
    "extended range", "extended-range", "ER munition",
    "extended-range artillery", "extended-range rocket",
    "guided rocket", "precision rocket", "GMLRS",
    
    # Components
    "scramjet", "scramjet propulsion", "ramjet",
    "solid propulsion", "solid rocket motor",
    "seeker", "RF seeker", "radar seeker",
    "IR seeker", "infrared seeker", "imaging seeker",
    "dual-mode seeker", "multi-mode seeker", "MMW seeker",
    "warhead", "penetrating warhead", "submunition",
    "guidance", "guidance section", "guidance kit",
    "INS/GPS", "INS-GPS", "INS-GNSS", "GPS-aided INS",
    "terminal guidance", "midcourse guidance",
    "weapon datalink", "man-in-the-loop",
    
    # Software
    "strike mission planning", "target planning",
    "kill-chain", "kill chain", "kill-chain software",
    "ISR-to-strike", "ISR to strike",
    "weapon-target pairing", "weapon target pairing",
    
    # Infrastructure
    "missile launcher", "ground launcher", "mobile launcher", "TEL",
    "air launcher", "aircraft pylon",
    "sea launcher", "ship launcher",
    "munitions storage",
    
    # Services
    "seeker development", "guidance development",
    "hypersonic R&D", "hypersonic research",
    "range instrumentation", "tracking instrumentation",
}

# Domain 10: Space
SPACE_KEYWORDS = {
    # Satellites
    "satellite", "spacecraft",
    "small-sat", "smallsat", "small satellite",
    "cubesat", "nanosat", "microsat", "minisat",
    "communication satellite", "comms satellite", "SATCOM",
    "ISR satellite", "reconnaissance satellite", "recce satellite",
    "SAR satellite", "radar satellite",
    "EO satellite", "optical satellite", "imaging satellite",
    "early warning satellite", "early-warning satellite",
    "navigation satellite", "PNT satellite", "GNSS satellite",
    "SIGINT satellite", "ELINT satellite",
    "satellite constellation", "constellation",
    "LEO constellation", "MEO", "GEO",
    "in-orbit servicing", "orbital servicing",
    
    # Launch
    "launch vehicle", "rocket", "space launch",
    "responsive launch", "rapid launch",
    "satellite launch", "payload launch",
    "small launch vehicle", "SLV",
    "reusable launch vehicle", "RLV",
    
    # Payloads
    "space-based EO", "space-based IR", "space-based SAR",
    "space-based SIGINT", "space payload",
    "optical communications", "laser communications",
    "optical inter-satellite link", "OISL",
    
    # Components
    "satellite bus", "spacecraft bus",
    "satellite propulsion", "electric propulsion",
    "star tracker", "star-tracker",
    "radiation hardened", "radiation-hardened", "rad-hard",
    "space-qualified", "space qualified",
    "solar array", "solar panel",
    
    # Software
    "constellation tasking", "satellite tasking",
    "on-board processing", "onboard processing",
    "ground-processing pipeline", "ground processing",
    
    # Ground Segment
    "ground station", "satellite ground station", "earth station",
    "mission control centre", "MCC", "satellite operations",
    "TT&C", "telemetry tracking command",
    "launch infrastructure", "launch complex",
    "satellite antenna", "ground antenna",
    "VSAT", "satellite terminal",
    
    # Services
    "launch services", "launch service provider",
    "satellite imagery", "imagery subscription",
    "data subscription", "bandwidth lease",
    "space-based ISR", "commercial imagery",
    "ground-segment-as-a-service",
}

# Domain 11: SSA/SDA
SSA_SDA_KEYWORDS = {
    # Systems
    "space situational awareness", "SSA",
    "space domain awareness", "SDA",
    "space surveillance", "space tracking",
    "space surveillance radar",
    "optical telescope", "electro-optical telescope",
    "space-based surveillance sensor",
    "object tracking", "object tracking space",
    "debris tracking", "space debris",
    
    # Components
    "large-aperture optics", "large aperture optics",
    "tracking mount", "telescope mount",
    "timing system", "precise timing",
    
    # Software
    "object cataloguing", "object catalog", "space catalog",
    "conjunction analysis", "collision analysis",
    "manoeuvre detection", "maneuver detection",
    "AI tracking", "ML tracking",
    "attribution", "threat attribution",
    
    # Infrastructure
    "SSA operations centre", "SSA operations center",
    "sensor site", "tracking site",
    "data fusion node", "fusion centre",
    
    # Services
    "counter-space studies", "counter-space", "space control",
    "space threat assessment",
}

# Domain 12: AI/ML
AI_ML_KEYWORDS = {
    # Core
    "artificial intelligence", "AI system",
    "machine learning", "ML model",
    "deep learning", "neural network", "DNN", "CNN",
    "computer vision", "image recognition",
    "automatic target recognition", "ATR",
    "automated target recognition",
    "automatic detection", "auto-detection",
    "object detection", "target detection",
    "image classification", "video analytics",
    
    # Fusion/Decision
    "sensor fusion", "data fusion", "multi-sensor fusion",
    "sensor-fusion engine", "fusion engine",
    "decision support", "decision-support", "decision aid",
    "recommendation system", "decision recommendation",
    "predictive maintenance", "predictive analytics",
    "anomaly detection", "pattern recognition",
    
    # NLP
    "NLP", "natural language processing",
    "text analytics", "text mining",
    "intel triage", "intelligence triage",
    "generative AI", "generative analysis",
    "LLM", "large language model",
    
    # Edge/Embedded
    "edge AI", "edge-AI", "edge inference",
    "embedded AI", "embedded ML",
    "on-device AI", "real-time AI",
    
    # Infrastructure
    "GPU cluster", "GPU compute",
    "AI accelerator", "ML accelerator", "TPU",
    "inference engine", "inference hardware",
    "accelerator hardware",
    "edge-compute kit", "edge compute kit",
    "MLOps", "ML operations",
    "data-labelling platform", "data labeling platform",
    "secure data lake", "data lake",
    
    # Data
    "data labelling", "data labeling", "annotation",
    "training data", "labeled data",
    
    # Services
    "model development", "ML model development",
    "algorithm challenge", "AI challenge",
    "AI testing", "AI assurance",
    "analytics-as-a-service", "AI-as-a-service",
    "model hosting", "ML hosting",
    "AI platform", "ML platform",
}

# Domain 13: Cyber
CYBER_KEYWORDS = {
    # Defensive
    "cybersecurity", "cyber security", "cyber defence", "cyber defense",
    "SOC", "security operations centre", "security operations center",
    "SIEM", "security information event management",
    "EDR", "endpoint detection", "endpoint detection response",
    "XDR", "extended detection response",
    "network monitoring", "network security monitoring",
    "intrusion detection", "IDS", "intrusion detection system",
    "intrusion prevention", "IPS",
    "threat intelligence", "cyber threat intelligence",
    "threat-intelligence platform", "TIP",
    "malware analysis", "malware detection",
    "zero trust", "zero-trust", "zero trust architecture",
    "network segmentation", "microsegmentation",
    "encryption", "data encryption",
    "cryptography", "cryptographic",
    "PKI", "public key infrastructure",
    "secure gateway", "security gateway",
    "firewall", "next-gen firewall", "NGFW",
    "HSM", "hardware security module",
    "secure OS", "secure operating system", "hardened OS",
    
    # Offensive
    "penetration testing", "pentest", "pen test",
    "red team", "red-team", "red teaming",
    "vulnerability assessment", "vulnerability scan",
    "security audit", "security assessment",
    "exploitation tooling", "exploit development",
    "red-team framework", "red team framework",
    
    # Infrastructure
    "SOC infrastructure", "cyber infrastructure",
    "air-gapped", "air gapped", "air-gapped network",
    "secure enclave", "classified network",
    
    # OT/ICS
    "OT security", "operational technology security",
    "ICS security", "industrial control system security",
    "SCADA security", "SCADA",
    
    # Services
    "cyber range", "cyber training", "cyber exercise",
    "SOC-as-a-service", "SOC as a service", "managed SOC",
    "incident response", "IR services",
    "vulnerability research", "security research",
    
    # TEMPEST
    "TEMPEST", "tempest shielding",
    "emission security", "EMSEC", "emanations security",
}

# Domain 14: Quantum
QUANTUM_KEYWORDS = {
    # Core
    "quantum", "quantum technology",
    "quantum computing", "quantum computer",
    "quantum processor", "qubit",
    
    # Sensors
    "quantum sensor", "quantum sensing",
    "quantum gravimeter", "quantum gravity sensor",
    "quantum magnetometer", "quantum magnetic sensor",
    "quantum clock", "atomic clock",
    "quantum imaging",
    
    # Navigation
    "quantum navigation", "quantum inertial",
    "quantum-inertial navigation", "quantum INS",
    "quantum PNT", "quantum positioning",
    
    # Communications
    "quantum key distribution", "QKD",
    "quantum encryption", "quantum cryptography",
    "post-quantum cryptography", "PQC",
    "quantum-resistant", "quantum safe",
    "quantum communication", "quantum network",
    "QKD stack", "QKD system", "QKD link",
    
    # Other
    "quantum radar", "quantum-computing algorithm",
    "quantum testbed", "quantum lab",
    "PQC migration", "quantum migration",
    "quantum-sensing prototype", "quantum prototype",
}

# Domain 15: Cognitive/IO
COGNITIVE_IO_KEYWORDS = {
    # OSINT
    "OSINT", "open source intelligence",
    "OSINT collection", "OSINT monitoring",
    
    # IO
    "information operations", "IO",
    "information warfare", "IW",
    "psychological operations", "PSYOP", "psyops",
    "influence operations", "influence campaign",
    
    # Social Media
    "social media monitoring", "social media analytics",
    "social-media analytics", "social listening",
    
    # Disinformation
    "disinformation", "misinformation",
    "fake news detection", "false information",
    "narrative detection", "narrative analysis",
    "narrative-resilience", "narrative resilience",
    
    # Deepfake
    "deepfake", "deepfake detection",
    "synthetic media", "synthetic content",
    
    # Analysis
    "sentiment analysis", "opinion mining",
    "influence-mapping", "influence mapping",
    "network analysis", "social network analysis",
    "media monitoring", "media analysis",
    
    # Infrastructure
    "analysis platform", "analytics platform",
    "secure collection", "secure collection infrastructure",
    
    # Services
    "information-environment assessment",
    "psychological-operations support",
    "analyst training", "OSINT training",
}

# Domain 16: Enablers
ENABLERS_KEYWORDS = {
    # Communications
    "tactical radio", "tactical communications",
    "HF radio", "VHF radio", "UHF radio",
    "manpack radio", "man-portable radio",
    "vehicular radio", "vehicle radio",
    "airborne radio", "naval radio",
    "cognitive radio",
    "frequency hopping", "spread spectrum",
    "ECCM radio", "jam-resistant radio",
    "mesh network", "mesh radio", "MANET",
    "mobile ad-hoc", "mobile ad hoc network",
    "tactical datalink", "tactical data link",
    "data link", "datalink",
    "beyond line of sight", "BLOS",
    "SATCOM datalink",
    "5G military", "private 5G", "5G network",
    "private network", "LTE military",
    
    # PNT
    "navigation system", "nav system",
    "inertial navigation", "INS", "inertial nav",
    "GPS receiver", "GNSS receiver",
    "anti-jam GPS", "anti-jam GNSS",
    "resilient PNT", "assured PNT",
    
    # C2
    "common operating picture", "COP",
    "battle-management software", "BMS",
    "integration backbone", "C2 backbone",
    "kill web", "kill-web",
    "command and control", "C2",
    "C4ISR", "C4I",
    
    # Test
    "test range", "firing range", "instrumented range",
    "range instrumentation", "telemetry",
    "trials support", "test support",
    "certification", "qualification",
    
    # Data
    "secure cloud", "classified cloud",
    "data fabric", "data infrastructure",
    
    # Power
    "mobile power", "generator",
    
    # Simulation
    "simulator", "flight simulator", "combat simulator",
    "war gaming", "wargaming", "war game",
    "mission rehearsal", "mission planning",
    "synthetic training", "synthetic environment",
    "virtual training", "constructive simulation",
}

# Intelligence Equipment (ITEMS - affects classification)
INTELLIGENCE_EQUIPMENT_KEYWORDS = {
    # Crypto/COMSEC
    "cryptographic", "crypto device", "crypto equipment",
    "cipher", "cipher device", "cipher machine",
    "COMSEC", "communications security",
    "secure voice", "secure data",
    "secure communication", "encrypted communication",
    "key management", "key loader", "key fill",
    "encryption device", "encryptor",
    "bulk encryptor", "link encryptor",
    
    # C4ISR
    "battle management system", "BMS",
    "tactical data link", "Link 16", "Link 22",
    "combat management system", "CMS",
    
    # ISR Platforms
    "ISTAR", "ISR platform", "ISR aircraft",
    "reconnaissance aircraft", "recce aircraft",
    "surveillance aircraft", "patrol aircraft",
    "LOROP", "long range oblique photography",
    "aerial reconnaissance", "strategic reconnaissance",
    
    # Night Vision
    "thermal imager", "thermal imaging", "TI",
    "thermal sight", "thermal camera",
    "night vision", "NVD", "night vision device",
    "night sight", "night observation",
    "image intensifier", "I2",
    "uncooled thermal", "cooled thermal",
    "FLIR", "forward looking infrared",
    "electro-optic", "electro-optical", "EO",
    "EO system", "EO/IR", "EO-IR",
    "IR sensor", "infrared sensor",
    "MWIR", "mid-wave infrared",
    "LWIR", "long-wave infrared",
    "SWIR", "short-wave infrared",
    "laser range finder", "LRF",
    "spotter scope", "observation scope",
    "night binocular", "periscope", "driver periscope",
    
    # Surveillance
    "coastal surveillance", "maritime surveillance",
    "border surveillance", "perimeter surveillance",
    "battlefield surveillance",
    "AIS", "automatic identification system",
    "vessel tracking", "ship tracking",
    "maritime domain awareness", "MDA",
    "unattended ground sensor", "UGS", "remote sensor",
    
    # Antennas & RF
    "antenna array", "phased array",
    "AESA", "active electronically scanned",
    "wideband antenna", "broadband antenna",
    "DF antenna", "direction finding antenna",
    "circular array", "Adcock antenna",
    "Watson-Watt antenna", "crossed loop",
    "horn antenna", "parabolic antenna",
    "dipole", "monopole",
    "omni-directional", "directional antenna",
    "HF antenna", "VHF antenna", "UHF antenna",
    "microwave antenna", "radome",
    "RF front end", "RF module",
    "low noise amplifier", "LNA",
    "preselector", "RF filter",
    "bandpass filter", "notch filter",
    "power amplifier", "PA",
    "travelling wave tube", "TWT",
    
    # Receivers & Processing
    "superheterodyne", "digital receiver",
    "channelized receiver", "IFM receiver",
    "instantaneous frequency measurement",
    "crystal video receiver",
    "panoramic receiver", "intercept receiver",
    "I/Q receiver", "coherent receiver",
    "digital signal processor", "DSP",
    "FPGA", "field programmable",
    "analog to digital converter", "ADC",
    "fast Fourier transform", "FFT",
    "spectrum analyzer", "spectrum analyser",
    "vector signal analyzer",
    "signal generator", "frequency synthesizer",
    
    # Sensors
    "CCD sensor", "CMOS sensor",
    "focal plane array", "FPA",
    "microbolometer",
    "InSb detector", "MCT detector", "HgCdTe",
    "Gen III image intensifier", "Gen II",
    "photomultiplier",
    
    # Radar
    "radar transceiver", "radar processor",
    "radar signal processor",
    "doppler processor", "pulse doppler",
    "MTI", "moving target indicator",
    "pulse compression", "frequency agility",
    "low probability of intercept", "LPI",
    "track while scan", "TWS",
    "IFF", "identification friend or foe",
    "Mode S", "Mode 5", "Mode 4",
    "transponder", "interrogator", "beacon",
}


# =============================================================================
# ROUTINE INDICATORS - These confirm ROUTINE classification
# =============================================================================

ROUTINE_KEYWORDS = {
    # Civil Works
    "whitewashing", "colour washing", "color washing",
    "painting building", "wall painting",
    "road repair", "drain repair", "plumbing",
    "sanitation", "sewage",
    "toilet construction", "bathroom", "septic tank",
    "boundary wall", "compound wall", "fencing", "gate repair",
    "roofing", "roof repair", "waterproofing", "flooring",
    
    # MT/Vehicle (routine)
    "denting and painting", "denting painting",
    "tyre", "tire", "battery vehicle",
    "vehicle servicing", "car servicing",
    "POL", "petrol oil lubricant", "lubricant", "diesel",
    "vehicle spare", "auto spare",
    "auto electrical", "vehicle washing",
    
    # Furniture/Office
    "furniture", "chair", "table", "desk",
    "almirah", "cupboard", "cabinet",
    "office equipment", "stationery", "printer cartridge",
    "air conditioner", "AC maintenance", "AC repair",
    "fan", "ceiling fan", "cooler", "desert cooler",
    
    # Provisions
    "ration", "grocery", "groceries",
    "canteen", "mess", "kitchen",
    "cooking", "utensil", "crockery", "cutlery",
    "tea", "coffee", "snacks", "catering",
    "food supply", "dry ration",
    
    # Clothing
    "uniform", "clothing", "dress material",
    "bedding", "linen", "blanket",
    "mattress", "pillow", "curtain", "towel",
    
    # Grounds
    "gardening", "horticulture", "grass cutting",
    "lawn", "lawn mower",
    "tree plantation", "landscaping", "hedge cutting",
    
    # Sports
    "sports equipment", "sports goods",
    "gymnasium", "gym equipment", "fitness",
    "sports ground", "playground",
    "basketball", "volleyball", "football", "cricket",
    "badminton", "tennis",
    
    # Medical (routine)
    "dispensary", "OPD", "ambulance", "stretcher",
    "first aid", "first-aid",
    "medicine", "pharmaceutical", "medical supplies",
    
    # Miscellaneous
    "printing", "photocopying", "binding",
    "housekeeping", "cleaning", "sweeping", "garbage",
    "pest control", "fumigation",
    "security guard", "watchman", "manpower supply",
    "laundry", "washing",
}


# =============================================================================
# METADATA-ONLY KEYWORDS (Captured but don't affect classification)
# =============================================================================

UNIT_ORG_KEYWORDS = {
    # Army
    "DGMI", "Directorate General Military Intelligence",
    "Military Intelligence", "MI", "Corps of Intelligence",
    "Field Intelligence Unit", "FIU",
    "Counter Intelligence", "CI",
    "Signal Regiment", "Signal Battalion", "Corps of Signals",
    
    # Navy
    "DNI", "Directorate of Naval Intelligence",
    "Naval Intelligence", "INAS", "Naval Air Squadron",
    "IMAC", "Information Management and Analysis Centre",
    "IFC-IOR", "Information Fusion Centre",
    "MARCOS", "Marine Commando",
    "Naval Armament Depot", "NAD",
    
    # Air Force
    "Wireless Experimental Unit", "WEU",
    "No. 41 WEU", "No. 42 WEU", "No. 43 WEU",
    "No. 44 WEU", "No. 45 WEU", "No. 46 WEU",
    "Signal Unit", "SU",
    
    # Tri-Service
    "Defence Intelligence Agency", "DIA",
    "Joint Cipher Bureau", "JCB",
    "DIPAC", "NTRO", "National Technical Research",
    "Defence Cyber Agency", "DCyA", "DCA",
    "Defence Space Agency", "DSA",
    "Aviation Research Centre", "ARC",
    
    # Scouts
    "Ladakh Scouts", "Arunachal Scouts", "Sikkim Scouts",
    
    # Organizations (context only)
    "DRDO", "Defence Research and Development",
    "BEL", "Bharat Electronics",
    "HAL", "Hindustan Aeronautics",
    "BDL", "Bharat Dynamics",
    "MDL", "Mazagon Dock",
    "GRSE", "Garden Reach Shipbuilders",
    "GSL", "Goa Shipyard",
    "OFB", "Ordnance Factory",
    "LRDE", "DLRL", "CABS", "IRDE", "DEAL", "SAG",
}


# =============================================================================
# DOMAIN MAPPING (Only ITEM keywords - for classification)
# =============================================================================

DOMAIN_KEYWORD_MAP = {
    "UAS": UAS_KEYWORDS,
    "USV": USV_KEYWORDS,
    "UUV": UUV_KEYWORDS,
    "UGV": UGV_KEYWORDS,
    "C-UAS": COUNTER_UAS_KEYWORDS,
    "AIR_DEFENCE": AIR_DEFENCE_KEYWORDS,
    "DEW": DEW_KEYWORDS,
    "EW_SIGINT": EW_SIGINT_KEYWORDS,
    "STRIKE": STRIKE_KEYWORDS,
    "SPACE": SPACE_KEYWORDS,
    "SSA_SDA": SSA_SDA_KEYWORDS,
    "AI_ML": AI_ML_KEYWORDS,
    "CYBER": CYBER_KEYWORDS,
    "QUANTUM": QUANTUM_KEYWORDS,
    "COGNITIVE_IO": COGNITIVE_IO_KEYWORDS,
    "ENABLERS": ENABLERS_KEYWORDS,
    "INTELLIGENCE_EQUIPMENT": INTELLIGENCE_EQUIPMENT_KEYWORDS,
}


# =============================================================================
# v2.0 TAXONOMY RECONCILIATION  (additive — makes this a strict superset of the
# v2.0 master taxonomy .md). Broadens coverage only; removes nothing.
# NOTE: bare "certificate" from v2.0 CYBER is INTENTIONALLY EXCLUDED — as a
# standalone word it false-positives heavily on routine tenders (test /
# experience / ISO certificates). PKI/crypto context is already covered.
# =============================================================================
UAS_KEYWORDS.update({"drone mission","drone weapon","precision munition"})
UUV_KEYWORDS.update({"unmanned underwater","underwater sensor","mine detection payload",
    "underwater navigation","inertial navigation underwater","docking station UUV",
    "charging station underwater","launch and recovery","LARS"})
UGV_KEYWORDS.update({"autonomous ground","autonomous navigation ground","LiDAR terrain",
    "optionally manned vehicle","robotic logistics","self-driving military","unmanned logistics"})
COUNTER_UAS_KEYWORDS.update({"acoustic drone detection","counter-drone HPM","drone spoofing","drone tracking"})
AIR_DEFENCE_KEYWORDS.update({"battle management","gun system air defence","surface-to-air"})
DEW_KEYWORDS.update({"adaptive optics weapon","laser power","laser system","thermal management laser"})
STRIKE_KEYWORDS.update({"base bleed","CCF","course correction fuze","datalink weapon",
    "extended range artillery","mission planning strike","precision fuze","rocket assisted","targeting software"})
SPACE_KEYWORDS.update({"collision avoidance space","laser comms space","optical communications space",
    "rocket launch","satellite payload"})
CYBER_KEYWORDS.update({"cyber threat","industrial control"})
COGNITIVE_IO_KEYWORDS.update({"content analysis","network analysis social"})
INTELLIGENCE_EQUIPMENT_KEYWORDS.update({"C2 system","fence sensor"})
ENABLERS_KEYWORDS.update({"DRDO range","integrated test range","ITR","tracking radar range"})
NAMED_SYSTEMS.update({"Netra UAV","VSHORAD"})
ROUTINE_KEYWORDS.update({"annual maintenance"})


# =============================================================================
# CLASSIFIER
# =============================================================================

@dataclass
class ClassificationResult:
    classification: str  # "CRITICAL" or "ROUTINE"
    confidence: float
    matched_keywords: List[str]
    domains: List[str]
    named_system_match: Optional[str] = None
    unit_org_matches: List[str] = field(default_factory=list)  # Metadata only


class ProcurementClassifier:
    """
    Classify defense procurement tenders as CRITICAL or ROUTINE.
    
    Logic:
    - If ITEM matches CRITICAL keywords → CRITICAL
    - Otherwise → ROUTINE (default)
    
    Unit/Org keywords are captured as metadata but DO NOT affect classification.
    """
    
    def __init__(self):
        # Build critical keyword set (ITEMS only)
        self.critical_keywords: Set[str] = set()
        for keywords in DOMAIN_KEYWORD_MAP.values():
            self.critical_keywords.update(kw.lower() for kw in keywords)
        
        self.named_systems = {s.lower(): s for s in NAMED_SYSTEMS}
        self.routine_keywords = {kw.lower() for kw in ROUTINE_KEYWORDS}
        self.unit_org_keywords = {kw.lower(): kw for kw in UNIT_ORG_KEYWORDS}
    
    def classify(self, text: str) -> ClassificationResult:
        """Classify a tender text as CRITICAL or ROUTINE."""
        text_lower = text.lower()
        matched_critical = []
        matched_routine = []
        unit_org_matches = []
        named_match = None
        
        # Extract unit/org matches (METADATA ONLY)
        for kw_lower, kw_original in self.unit_org_keywords.items():
            if self._word_match(kw_lower, text_lower):
                unit_org_matches.append(kw_original)
        
        # Check named systems (highest priority for CRITICAL)
        for sys_lower, sys_original in self.named_systems.items():
            if self._word_match(sys_lower, text_lower):
                named_match = sys_original
                matched_critical.append(f"[SYSTEM] {sys_original}")
                break
        
        # Check ITEM keywords (what's being procured)
        for keyword in self.critical_keywords:
            if self._word_match(keyword, text_lower):
                if keyword not in [m.lower() for m in matched_critical]:
                    matched_critical.append(keyword)
        
        # Check routine keywords
        for keyword in self.routine_keywords:
            if self._word_match(keyword, text_lower):
                matched_routine.append(keyword)
        
        # CLASSIFICATION LOGIC
        # CRITICAL only if ITEM matches critical keywords
        # Routine keywords do NOT override critical (whitewashing for radar still = critical if radar mentioned)
        
        if matched_critical:
            if named_match:
                confidence = 1.0
            else:
                confidence = min(0.95, 0.5 + len(matched_critical) * 0.1)
            
            domains = self._get_domains(matched_critical)
            
            return ClassificationResult(
                classification="CRITICAL",
                confidence=confidence,
                matched_keywords=matched_critical[:15],
                domains=domains,
                named_system_match=named_match,
                unit_org_matches=unit_org_matches[:5]
            )
        else:
            # No critical items found → ROUTINE
            confidence = 0.9 if matched_routine else 0.7
            
            return ClassificationResult(
                classification="ROUTINE",
                confidence=confidence,
                matched_keywords=matched_routine[:5],
                domains=[],
                named_system_match=None,
                unit_org_matches=unit_org_matches[:5]
            )
    
    def _word_match(self, keyword: str, text: str) -> bool:
        """Match keyword with word boundaries."""
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _get_domains(self, matched_keywords: List[str]) -> List[str]:
        """Map matched keywords to domain categories."""
        domains = set()
        for keyword in matched_keywords:
            kw_clean = keyword.lower().replace("[system] ", "")
            for domain, keywords in DOMAIN_KEYWORD_MAP.items():
                if kw_clean in {k.lower() for k in keywords}:
                    domains.add(domain)
        return sorted(domains)
    
    def batch_classify(self, texts: List[str]) -> List[ClassificationResult]:
        """Classify multiple tenders."""
        return [self.classify(text) for text in texts]
    
    def get_stats(self) -> Dict:
        """Get keyword statistics."""
        stats = {
            "named_systems": len(NAMED_SYSTEMS),
            "total_critical_keywords": len(self.critical_keywords),
            "routine_keywords": len(self.routine_keywords),
            "unit_org_keywords": len(UNIT_ORG_KEYWORDS),
            "domains": {}
        }
        for domain, keywords in DOMAIN_KEYWORD_MAP.items():
            stats["domains"][domain] = len(keywords)
        return stats


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def classify_tender(text: str) -> ClassificationResult:
    """Quick classification of a single tender."""
    return ProcurementClassifier().classify(text)


def is_critical(text: str) -> bool:
    """Check if a tender is CRITICAL."""
    return classify_tender(text).classification == "CRITICAL"


def get_all_critical_keywords() -> Set[str]:
    """Get complete set of CRITICAL keywords."""
    return ProcurementClassifier().critical_keywords


def get_keyword_count() -> int:
    """Get total unique critical keywords."""
    return len(get_all_critical_keywords())


# =============================================================================
# MAIN - VERIFICATION
# =============================================================================

if __name__ == "__main__":
    classifier = ProcurementClassifier()
    stats = classifier.get_stats()
    
    print("=" * 70)
    print("PROCUREMENT CLASSIFICATION SYSTEM - FINAL VERSION")
    print("=" * 70)
    print(f"\nNamed Indian Systems: {stats['named_systems']}")
    print(f"Total Critical Item Keywords: {stats['total_critical_keywords']}")
    print(f"Routine Keywords: {stats['routine_keywords']}")
    print(f"Unit/Org Keywords (metadata only): {stats['unit_org_keywords']}")
    print("\nKeywords by Domain:")
    print("-" * 40)
    for domain, count in sorted(stats['domains'].items()):
        print(f"  {domain:25} : {count:4}")
    print("-" * 40)
    print(f"  {'TOTAL':25} : {sum(stats['domains'].values()):4}")
    
    # Test the key scenarios
    print("\n" + "=" * 70)
    print("CLASSIFICATION TESTS")
    print("=" * 70)
    
    test_cases = [
        # Should be ROUTINE (cleaning/admin for defense org)
        ("Housekeeping services for DRDO LRDE Bangalore", "ROUTINE"),
        ("Whitewashing of NAD Visakhapatnam building", "ROUTINE"),
        ("Supply of ration items for Signal Regiment", "ROUTINE"),
        ("Canteen supplies for WEU Charbatia", "ROUTINE"),
        ("AC maintenance at BEL Ghaziabad", "ROUTINE"),
        ("Security guard services for DLRL Hyderabad", "ROUTINE"),
        
        # Should be CRITICAL (actual systems/equipment)
        ("Procurement of Samyukta EW System", "CRITICAL"),
        ("Supply of thermal imager for DRDO", "CRITICAL"),
        ("Counter-drone radar for NAD", "CRITICAL"),
        ("UAV ground control station", "CRITICAL"),
        ("Quantum key distribution system", "CRITICAL"),
        ("SIGINT receiver for Signal Regiment", "CRITICAL"),
        ("Repair of night vision devices", "CRITICAL"),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = classifier.classify(text)
        status = "✓" if result.classification == expected else "✗"
        if result.classification != expected:
            all_passed = False
        
        print(f"\n{status} [{result.classification}] (expected {expected})")
        print(f"  Text: {text}")
        if result.unit_org_matches:
            print(f"  Unit/Org (metadata): {', '.join(result.unit_org_matches)}")
        if result.matched_keywords:
            print(f"  Keywords: {', '.join(result.matched_keywords[:3])}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 70)
