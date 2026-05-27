"""
species.py — Fish species definitions for Aquarium 98.

Each entry drives both rendering (sheet, colors, aspect) and simulation
(speed, sociable, layer_pref, bottom/crawler).

Extra optional fields (used by UI panels):
  fun_facts   list[str]   2-3 real/invented facts shown in the Fish Profile popup.
  rare        bool        If True, spawn-limited to MAX_RARE_IN_TANK at once.
                          Uses the generic fish_N_new.png sheets as mystery fish.
"""
from __future__ import annotations

MAX_RARE_IN_TANK = 1   # hard cap: at most one rare fish in the tank at a time

# Each species references one of the available fish sprite sheets.
SPECIES: list[dict] = [
    # ── Clownfish ──────────────────────────────────────────────────────────
    dict(name="Clownfish",  body=(255, 140, 30),  fin=(255, 255, 255), accent=(255, 255, 255),
         size=7,  speed=18, sociable=True,  pattern="stripes",  aspect=1.10, fin_style="normal",
         school_size=2, layer_pref=1, sheet="Clown_Fish.png",
         fun_facts=[
             "Clownfish are all born male — the dominant fish in a group changes sex to become female.",
             "They are immune to the stinging cells of their host anemone due to a special mucus coating.",
             "In the wild, a clownfish rarely strays more than a few meters from its home anemone.",
         ]),

    # ── Regal Tang (Blue Tang) ─────────────────────────────────────────────
    # Bright blue body, yellow tail.  Fast, active schooler in open water.
    dict(name="RegalTang",  body=(40, 90, 220),   fin=(255, 220, 40),  accent=(20, 20, 40),
         size=8,  speed=22, sociable=True,  pattern="topband",  aspect=1.25, fin_style="normal",
         school_size=3, layer_pref=1, sheet="RegalTang_Fish.png"),

    # ── Yellow Tang ────────────────────────────────────────────────────────
    # Uniform bright yellow.  Peaceful mid-column schooler.
    dict(name="YellowTang", body=(255, 210, 30),  fin=(255, 180, 20),  accent=(220, 160, 10),
         size=7,  speed=20, sociable=True,  pattern="none",     aspect=1.30, fin_style="normal",
         school_size=3, layer_pref=2, sheet="YellowTang_Fish.png"),

    # ── Angelfish ──────────────────────────────────────────────────────────
    # Tall, disc-shaped body.  Elegant slow swimmer, solitary.
    dict(name="Angelfish",  body=(245, 245, 255), fin=(50, 50, 80),    accent=(30, 30, 40),
         size=10, speed=14, sociable=False, pattern="stripes",  aspect=1.50, fin_style="big",
         uncommon=True, layer_pref=2, sheet="Angel_Fish.png"),

    # ── Emperor Angelfish ──────────────────────────────────────────────────
    # Striking blue + yellow striped adult.  Semi-territorial, mid depth.
    dict(name="Emperor",    body=(70, 150, 230),  fin=(255, 210, 40),  accent=(255, 210, 40),
         size=9,  speed=15, sociable=False, pattern="stripes",  aspect=1.20, fin_style="normal",
         uncommon=True, layer_pref=2, sheet="Emperor_Fish.png",
         fun_facts=[
             "The Emperor Angelfish starts life with a completely different look: dark blue with white circles.",
             "It takes 3-4 years for the full adult coloration of blue stripes and yellow body to develop.",
             "Emperor Angelfish are highly intelligent and can recognize their feeder within a week.",
         ]),

    dict(name="Butterfly",  body=(255, 225, 80),  fin=(240, 200, 60),  accent=(20, 20, 40),
         size=7,  speed=18, sociable=True,  pattern="band",     aspect=1.25, fin_style="normal",
         uncommon=True, school_size=2, layer_pref=2, sheet="Butterfly_Fish.png",
         fun_facts=[
             "Butterfly Fish have a false eyespot near their tail to confuse predators about which end is the head.",
             "They are among the most faithful animals on Earth — pairs stay bonded for life.",
             "Their disc-shaped body lets them slip into coral crevices that predators cannot enter.",
         ]),

    dict(name="Lionfish",   body=(220, 90, 60),   fin=(255, 240, 210), accent=(245, 235, 210),
         size=9,  speed=10, sociable=False, pattern="stripes",  aspect=1.15, fin_style="big",
         uncommon=True, layer_pref=1, sheet="Lion_Fish.png",
         fun_facts=[
             "The Lionfish's feathery spines contain venom glands — but only dangerous to predators, not tankmates.",
             "Despite their fierce look, Lionfish are timid and prefer to ambush rather than actively chase prey.",
             "They can go weeks without eating, making them uniquely patient hunters.",
         ]),

    dict(name="Damsel",     body=(40, 120, 255),  fin=(20, 80, 200),   accent=(0, 40, 160),
         size=5,  speed=24, sociable=True,  pattern="none",     aspect=1.00, fin_style="normal",
         school_size=2, layer_pref=3, sheet="Damsel_Fish.png",
         fun_facts=[
             "Damselfish are famously territorial — a single 4-inch Damsel has been known to drive away much larger fish.",
             "They are one of only a few fish species known to actively 'farm' their own patches of algae.",
             "Despite their timid look in a tank, they are among the most aggressive per-inch-of-body fish in the ocean.",
         ]),

    dict(name="Cardinal",   body=(210, 40, 60),   fin=(255, 255, 255), accent=(255, 255, 255),
         size=6,  speed=16, sociable=True,  pattern="stripes",  aspect=1.10, fin_style="normal",
         school_size=3, layer_pref=2, sheet="Cardinal_Fish.png",
         fun_facts=[
             "Male Cardinal Fish are mouthbrooders — they hold fertilized eggs in their mouths until they hatch.",
             "They school in groups of thousands in the wild, forming shifting clouds of red and white.",
             "Cardinal Fish are naturally nocturnal but adapt well to daytime activity in a tank.",
         ]),

    dict(name="Puffer",     body=(230, 200, 80),  fin=(200, 170, 40),  accent=(60, 50, 20),
         size=8,  speed=8,  sociable=False, pattern="spots",    aspect=1.25, fin_style="normal",
         uncommon=True, layer_pref=2, sheet="Puffer_Fish.png",
         fun_facts=[
             "Puffer Fish inflate by swallowing water rapidly, expanding to over three times their resting size.",
             "Their beak-like teeth never stop growing and must be worn down by eating hard foods like shellfish.",
             "Despite containing enough toxin to kill 30 adult humans, Puffer Fish remain a delicacy in Japan.",
         ]),

    dict(name="Wrasse",     body=(80, 210, 200),  fin=(240, 90, 180),  accent=(240, 90, 180),
         size=6,  speed=26, sociable=True,  pattern="topband",  aspect=1.00, fin_style="normal",
         school_size=2, layer_pref=1, sheet="Wrasse_Fish.png",
         fun_facts=[
             "Wrasse set up 'cleaning stations' on the reef where other fish line up to be cleaned of parasites.",
             "They sleep buried under sand at night to protect themselves from nocturnal predators.",
             "Over 600 species of Wrasse exist — it is one of the most diverse fish families in the ocean.",
         ]),

    dict(name="Goldie",     body=(255, 170, 40),  fin=(255, 120, 20),  accent=(255, 255, 255),
         size=8,  speed=18, sociable=True,  pattern="none",     aspect=1.10, fin_style="normal",
         school_size=2, layer_pref=2, sheet="Goldie_Fish.png",
         fun_facts=[
             "Goldfish have a memory span of at least 3 months, thoroughly debunking the 3-second myth.",
             "They can recognize the faces of their owners and swim up excitedly when they approach.",
             "Wild goldfish are typically olive-green or brown — the iconic gold was selectively bred over centuries.",
         ]),

    dict(name="Neon",       body=(60, 200, 255),  fin=(255, 80, 140),  accent=(255, 40, 60),
         size=4,  speed=28, sociable=True,  pattern="topband",  aspect=1.00, fin_style="normal",
         school_size=4, layer_pref=3, sheet="Neon_Fish.png",
         fun_facts=[
             "The Neon Tetra's famous blue stripe is not pigment — it's caused by light reflecting off tiny crystals.",
             "They navigate using a lateral line organ that detects ripples from other fish's movements.",
             "In the wild, millions of Neon Tetras form a single school — the flickering acts like a super-organism.",
         ]),

    dict(name="Guppy",      body=(255, 100, 150), fin=(120, 200, 255), accent=(140, 210, 255),
         size=4,  speed=22, sociable=True,  pattern="spots",    aspect=1.00, fin_style="big",
         school_size=2, layer_pref=1, sheet="Guppy_Fish.png",
         fun_facts=[
             "Male Guppies have the most diverse color patterns of any species — no two males look exactly alike.",
             "Guppies can give birth to 20-200 live young every 30 days without needing a mate each time.",
             "They were the first tropical fish sent to space, surviving in weightless conditions.",
         ]),

    dict(name="Tetra",      body=(210, 50, 70),   fin=(20, 20, 40),    accent=(20, 20, 40),
         size=5,  speed=22, sociable=True,  pattern="none",     aspect=1.05, fin_style="normal",
         school_size=3, layer_pref=3, sheet="Tetra_Fish.png",
         fun_facts=[
             "Black Widow Tetras produce ultrasonic clicks to coordinate the school — inaudible to humans.",
             "They can shift color in milliseconds; stress, excitement, and sleep each produce different hues.",
             "Tetras have survived virtually unchanged for 5 million years — evolution decided to leave them alone.",
         ]),

    dict(name="Betta",      body=(180, 40, 200),  fin=(255, 80, 160),  accent=(255, 140, 200),
         size=9,  speed=11, sociable=False, pattern="none",     aspect=1.10, fin_style="big",
         uncommon=True, layer_pref=1, sheet="Betta_Fish.png",
         fun_facts=[
             "Male Bettas build elaborate bubble nests on the water's surface to house their eggs.",
             "They have a labyrinth organ that lets them breathe air directly — they can survive in low-oxygen water.",
             "Wild Bettas live in shallow rice paddies and can travel short distances overland during floods.",
         ]),

    dict(name="Catfish",    body=(120, 100, 80),  fin=(70, 55, 40),    accent=(60, 50, 30),
         size=11, speed=10, sociable=False, pattern="spots",    aspect=0.70, fin_style="low",
         bottom=True, algae_eater=True, layer_pref=1, sheet="Cat_Fish.png",
         fun_facts=[
             "Armored Catfish have bony plates instead of scales — tough enough to scratch glass.",
             "They can breathe through their intestine by swallowing air when oxygen levels drop dangerously low.",
             "A single Catfish can clean a heavily algaed tank overnight, but will starve without supplemental food.",
         ]),

    # ── Algae Eater (Siamese) ──────────────────────────────────────────────
    # Active scraper; algae_seeker flag gives it proportional grazing + growth suppression.
    dict(name="Algae Eater",  body=(80, 160, 200),  fin=(200, 140, 60), accent=(255, 180, 40),
         size=12, speed=12, sociable=False, pattern="topband", aspect=0.60, fin_style="low",
         bottom=True, algae_eater=True, algae_seeker=True, layer_pref=1,
         sheet="AlgaeEater_Fish.png",
         fun_facts=[
             "The Siamese Algae Eater is one of the only fish capable of eating red algae — a variety most species completely ignore.",
             "It uses a specialised sucker mouth to rasp algae directly off glass, rocks, and plant leaves; it is essentially always working.",
             "When algae runs low it shifts to biofilm and vegetable matter — offer blanched zucchini to keep it from getting hungry.",
             "Unlike the similar-looking Chinese Algae Eater, the Siamese variety stays peaceful well into adulthood.",
             "A single well-fed Algae Eater can visibly clear a heavily-fouled tank within 48 hours.",
         ]),

    # ── Zebra Danio ───────────────────────────────────────────────────────
    dict(name="Zebra Danio",  body=(100, 160, 230), fin=(255, 210, 80),  accent=(200, 230, 255),
         size=5, speed=32, sociable=True,  pattern="topband", aspect=0.95, fin_style="normal",
         school_size=4, layer_pref=1, sheet="Danio_Fish.png",
         fun_facts=[
             "Zebrafish were the first vertebrate to have their entire genome sequenced and are a cornerstone of medical research worldwide.",
             "They can regenerate heart tissue after injury — a capability scientists are actively studying for human cardiac therapies.",
             "Their blue and yellow stripes are actually silver-white; the 'blue' is structural colour produced by light diffraction off scale microstructures.",
         ]),

    # ── Harlequin Rasbora ─────────────────────────────────────────────────
    dict(name="Harlequin",    body=(80, 190, 200),  fin=(255, 200, 60),  accent=(255, 180, 40),
         size=5, speed=24, sociable=True,  pattern="band",    aspect=1.00, fin_style="normal",
         school_size=3, layer_pref=2, sheet="Rasbora_Fish.png",
         fun_facts=[
             "Harlequin Rasboras choose their spawning sites with unusual precision — they prefer specific leaf species and will reject substitutes.",
             "The dark triangle marking is thought to disrupt predator tracking by breaking up the silhouette when the school turns in unison.",
             "They are one of the most recommended first fish for beginners because they are extraordinarily tolerant of imperfect water conditions.",
         ]),

    # ── Kuhli Loach ───────────────────────────────────────────────────────
    dict(name="Kuhli Loach",  body=(210, 150, 50),  fin=(50, 35, 20),   accent=(20, 15, 5),
         size=9, speed=14, sociable=True,  pattern="stripes", aspect=0.32, fin_style="low",
         bottom=True, crawler=True, uncommon=True, school_size=2, layer_pref=1, sheet="KuhliLoach_Fish.png",
         fun_facts=[
             "Kuhli Loaches bury themselves completely in soft substrate — they can vanish for days and reappear only when lights go off.",
             "Despite looking like eels, they are true fish; their scales are simply so small they appear smooth from a distance.",
             "In the wild they live in cool, fast streams. Seeing one active during daylight in your tank is a sign of high comfort.",
         ]),

    # ── Honey Gourami ─────────────────────────────────────────────────────
    dict(name="Honey Gourami", body=(230, 160, 40), fin=(180, 100, 20), accent=(60, 30, 5),
         size=8, speed=13, sociable=False, pattern="none", aspect=1.30, fin_style="big",
         uncommon=True, layer_pref=2, sheet="HoneyGourami_Fish.png",
         fun_facts=[
             "The Honey Gourami breathes air through a labyrinth organ — it surfaces periodically for a gulp of air even in well-oxygenated water.",
             "Males build elaborate bubble nests at the surface and guard the eggs until hatching, a parenting role rare among fish.",
             "Wild Honey Gouramis are a pale, almost translucent cream; the vibrant honey-orange form was developed entirely through selective breeding.",
         ]),

    # ── Amano Shrimp ──────────────────────────────────────────────────────
    dict(name="Amano Shrimp",  body=(180, 160, 120), fin=(140, 120, 80), accent=(255, 200, 160),
         size=5, speed=16, sociable=True,  pattern="spots", aspect=0.70, fin_style="low",
         bottom=True, crawler=True, algae_eater=True, shrimp=True, school_size=2, layer_pref=1,
         sheet="Amano_Shrimp.png",
         fun_facts=[
             "Named after legendary aquarist Takashi Amano, this shrimp was his signature cleanup crew in world-famous planted tanks.",
             "Amano Shrimp cannot reproduce in freshwater — the larvae must drift to brackish water to survive, making captive breeding nearly impossible.",
             "They are fearless algae grazers, often seen clinging to plants and glass at improbable angles to reach every last green speck.",
             "An Amano Shrimp's tail fan is more than decoration — it can jet backward in a flash when startled, faster than most tankmates can react.",
         ]),

    # ── CPO Crayfish (Dwarf Mexican) ──────────────────────────────────────
    dict(name="CPO Crayfish",  body=(220, 120, 50), fin=(180, 80, 20),   accent=(255, 230, 180),
         size=7, speed=8,  sociable=False, pattern="none", aspect=0.80, fin_style="low",
         bottom=True, crawler=True, algae_eater=True, crayfish=True, layer_pref=1,
         sheet="DwarfMexican_Frog.png",
         fun_facts=[
             "CPO stands for 'Cambarellus patzcuarensis orange' — a dwarf crayfish from Lake Pátzcuaro in Mexico, one of its last wild strongholds.",
             "Unlike larger crayfish, the CPO is genuinely peaceful; it lacks the aggression to harm fish much bigger than itself.",
             "It molts its exoskeleton as it grows; during and just after molting it is extremely soft and vulnerable and hides completely.",
             "Female CPOs carry bright orange eggs under their tail fan for weeks, fanning them constantly with small swimming legs.",
             "The CPO is one of the only crayfish recommended for community tanks with small fish — a true freshwater curiosity.",
         ]),

    # ── African Dwarf Frog ────────────────────────────────────────────────
    dict(name="African Dwarf Frog", body=(60, 130, 70), fin=(100, 180, 80), accent=(200, 180, 40),
         size=8, speed=18, sociable=True,  pattern="spots", aspect=1.00, fin_style="low",
         bottom=True, frog=True, uncommon=True, school_size=2, layer_pref=1, sheet="AfricanDwarf_Frog.png",
         fun_facts=[
             "African Dwarf Frogs are fully aquatic — unlike most frogs, they cannot survive on land and must surface only to breathe air.",
             "They are nearly blind in bright light and locate food entirely by smell and the lateral-line vibration sense.",
             "When happy and well-fed, an African Dwarf Frog will perform a 'happy dance' — a rapid spinning swim with all four legs splayed wide.",
             "They are social animals and do best in pairs; a lone frog will often stop eating and become lethargic within weeks.",
             "Despite having lungs, they absorb most of their oxygen through thin, permeable skin — which is why water quality matters so much.",
         ]),

    # ══════════════════════════════════════════════════════════════════════
    # RARE SPECIES — fictional names, based loosely on real fish.
    # Spawned with low probability; at most MAX_RARE_IN_TANK in tank at once.
    # Each uses one of the generic fish_N_new.png sheets.
    # ══════════════════════════════════════════════════════════════════════

    # ── Dragon Goby (rare) ────────────────────────────────────────
    # Gobioides broussonnetii. Eel-like, iridescent silvery-blue, bottom-hugging.
    dict(name="Dragon Goby", body=(140, 170, 220), fin=(100, 130, 180), accent=(200, 210, 120),
         size=14, speed=9, sociable=False, pattern="none", aspect=0.45, fin_style="low",
         bottom=True, algae_eater=True, layer_pref=1, sheet="DragonGoby_Fish.png", rare=True,
         fun_facts=[
             "Despite its fearsome mouth full of sharp teeth, the Dragon Goby feeds almost entirely on algae — those teeth are for scraping, not fighting.",
             "It is nearly blind, relying on vibration and smell to find food; it will lose out to any faster tankmate at feeding time.",
             "In the wild it can reach 24 inches long, but in an aquarium rarely exceeds 15 inches. Yours is one of the lucky few kept in captivity.",
             "When healthy and well-lit, its scales develop a striking iridescent violet-blue shimmer with gold blotches unlike any other aquarium fish.",
             "Dragon Gobies are brackish-water specialists; they spend much of their time half-buried in the substrate, completely invisible.",
         ]),

    # ── Hermit Crab (rare) ───────────────────────────────────────
    dict(name="Hermit Crab", body=(200, 120, 50),  fin=(150, 80, 30),   accent=(240, 180, 100),
         size=7,  speed=5,  sociable=False, pattern="spots", aspect=1.00, fin_style="low",
         bottom=True, layer_pref=1, sheet="Hermit_Crab.png", rare=True, hermit_crab=True,
         fun_facts=[
             "Hermit crabs don't grow their own shells — they find and move into abandoned gastropod shells, trading up as they grow.",
             "They communicate by rubbing their shells together, a rasping sound used to negotiate shell swaps with neighbours.",
             "Hermit crabs have been observed forming orderly queues beside a desirable empty shell, waiting their turn to upgrade.",
             "In the wild they can live over 30 years, though most aquarium hermit crabs live far shorter lives due to improper salt levels.",
         ]),

    # ── Moonshell Hermit (super-rare) ─────────────────────────────
    dict(name="Moonshell Hermit", body=(210, 200, 240), fin=(170, 160, 210), accent=(255, 240, 200),
         size=8,  speed=4,  sociable=False, pattern="none", aspect=1.00, fin_style="low",
         bottom=True, layer_pref=1, sheet="Hermit_Crab_Rare.png",
         rare=True, super_rare=True, hermit_crab=True,
         fun_facts=[
             "The Moonshell Hermit’s pale, almost luminescent shell is believed to be from a species of moon snail found only in very deep water.",
             "Sightings in home aquaria are extraordinarily rare — most keepers go years without ever seeing one appear.",
             "Its lavender-tinted claws are thought to be an adaptation for low-light deep-sea environments; it is most active in the dark.",
             "Unlike common hermit crabs, the Moonshell Hermit rarely trades shells — it seems to form an unusual bond with its current home.",
             "Ancient Pacific islanders considered the pale hermit crab a symbol of patience and good fortune; finding one was considered a blessing.",
         ]),

    # ── Moonveil Dart (rare) ── based on reef damsels / chromis viridis ──
    dict(name="Moonveil Dart", body=(180, 220, 255), fin=(220, 240, 255), accent=(100, 160, 240),
         size=5,  speed=22, sociable=True,  pattern="topband",  aspect=1.05, fin_style="normal",
         layer_pref=3, sheet="fish_new.png", rare=True,
         fun_facts=[
             "Said to be an evolved form of reef damsels, the Moonveil Dart's silver-blue scales refract light into shifting patterns.",
             "Keepers report that this fish will rearrange small pebbles near its resting spot — a behavior science has yet to explain.",
             "Despite living in groups, each Moonveil Dart maintains a personal space of exactly three bubble-widths from any neighbor.",
         ]),

    # ── Prism Dancer (rare) ── based on harlequin rasbora / rainbowfish ──
    dict(name="Prism Dancer",  body=(160, 240, 200), fin=(255, 200, 80),  accent=(200, 100, 255),
         size=5,  speed=28, sociable=True,  pattern="stripes",  aspect=1.00, fin_style="normal",
         layer_pref=2, sheet="fish2_new.png", rare=True,
         fun_facts=[
             "The Prism Dancer's scales contain microscopic crystals that produce a holographic shimmer unlike any known species.",
             "Rarely seen alone — if you spot one, there are likely five more hiding in the tank plants nearby.",
             "Old sailors called them 'rainbow needles' and believed spotting one was a sign of exceptional good luck.",
         ]),

    # ── Golden Specter (rare) ── based on golden severum / discus ────────
    dict(name="Golden Specter", body=(255, 245, 180), fin=(240, 210, 80),  accent=(200, 170, 40),
         size=8,  speed=12, sociable=False, pattern="none",     aspect=1.35, fin_style="big",
         layer_pref=2, sheet="fish3_new.png", rare=True,
         fun_facts=[
             "The Golden Specter is nearly transparent when juvenile, gaining its golden hue only at full maturity.",
             "Believed to be distantly related to the Discus and Angelfish, its exact lineage has never been confirmed.",
             "So rarely encountered that the first documented photograph was only taken in 1987.",
         ]),

    # ── Crimson Fanveil (rare) ── based on ornate betta / fancy guppy ───
    dict(name="Crimson Fanveil", body=(200, 30, 60),  fin=(255, 100, 80),  accent=(255, 220, 180),
         size=8,  speed=11, sociable=False, pattern="stripes",  aspect=1.20, fin_style="big",
         layer_pref=1, sheet="fish4_new.png", rare=True,
         fun_facts=[
             "The Crimson Fanveil's flowing fins are multi-layered tissue that can fan to three times normal width when threatened.",
             "Unlike most fish, it appears to recognize its own reflection and will 'display' for mirrors.",
             "Bred from crossing wild betta lineages with deep-sea specimens, the result was so striking it nearly became a new genus.",
         ]),

    # ── Stone Glider (rare) ── based on plecostomus / armored catfish ────
    dict(name="Stone Glider",  body=(100, 90, 75),   fin=(60, 55, 45),    accent=(140, 120, 90),
         size=12, speed=8,  sociable=False, pattern="spots",    aspect=0.65, fin_style="low",
         bottom=True, algae_eater=True, layer_pref=1, sheet="fish5_new.png", rare=True,
         fun_facts=[
             "The Stone Glider's armored scales are among the hardest of any freshwater species — fossilized specimens were once mistaken for ancient lizard bones.",
             "Despite its imposing look, it feeds exclusively on algae and poses zero threat to other fish.",
             "It can remain completely motionless for up to 48 hours, fooling predators into thinking it is a rock.",
         ]),

    # ── Amber Wanderer (rare) ── based on horseshoe crab / sea cucumber ─
    dict(name="Amber Wanderer", body=(190, 130, 50),  fin=(140, 90, 30),   accent=(220, 170, 80),
         size=7,  speed=3,  sociable=False, pattern="spots",    aspect=1.00, fin_style="low",
         crawler=True, algae_eater=True, layer_pref=1, sheet="fish6_new.png", rare=True,
         fun_facts=[
             "The Amber Wanderer's warm glow comes from bioluminescent bacteria living in symbiosis within its shell.",
             "A single Amber Wanderer can clear a tank of algae more efficiently than three conventional cleanup fish.",
             "Ancient Chinese fishkeepers called it 'the patient one' — it is known to circle the same spot for days before moving on.",
         ]),

    # ── Celestial Pearl Rasbora (rare) ────────────────────────────────────
    dict(name="Pearl Rasbora", body=(80, 200, 180), fin=(255, 160, 40),  accent=(255, 230, 100),
         size=4, speed=20, sociable=True,  pattern="spots", aspect=1.00, fin_style="normal",
         layer_pref=2, sheet="Rasbora_Fish_Rare.png", rare=True,
         fun_facts=[
             "Discovered in 2006 in a single pond in Myanmar, the Celestial Pearl Danio immediately caused a collecting frenzy that nearly wiped out the entire wild population.",
             "Its pearl-white spots are not painted on the scales — they are windows through semi-transparent skin revealing white fat deposits underneath.",
             "Despite being under an inch long, the male performs one of the most elaborate courtship dances of any nano fish.",
             "Aquaculture farms took only two years to produce enough captive-bred specimens to satisfy global demand and protect the wild population.",
         ]),
]

# Names drawn for all new fish (bred or respawned) — guaranteed unique-feeling pool.
NAMES = [
    "Bubbles", "Goldie", "Finny", "Splash", "Nemo", "Dory", "Sushi", "Marlin",
    "Bubba", "Wanda", "Klaus", "Pebbles", "Coral", "Reef", "Jaws", "Tiny",
    "Sir Fin", "Lord Gill", "Captain", "Squirt", "Pearl", "Echo", "Mango", "Zippy",
    "Mochi", "Pixel", "Bit", "Zelda", "Link", "Sonic", "Kirby", "Toad",
    "Wasabi", "Ginger", "Plum", "Berry", "Tango", "Mambo", "Disco",
    "Ripple", "Drift", "Flash", "Glimmer", "Sparky", "Comet", "Zephyr", "Nova",
    "Pudding", "Biscuit", "Brine", "Salty", "Kelp", "Anchor", "Barnacle", "Phin",
    "Sundrop", "Moonbeam", "Starfish", "Riptide", "Shelly", "Sandy", "Misty",
    # Extended pool — gems & minerals
    "Topaz", "Onyx", "Garnet", "Opal", "Amber", "Crystal", "Cobalt", "Flint",
    # Space & cosmic
    "Cosmos", "Nebula", "Orbit", "Pulsar", "Astro", "Solaris", "Quasar", "Vega",
    # Nature
    "Willow", "Cedar", "Fern", "Moss", "Ivy", "Sage", "Basil", "Clover",
    # Spice rack
    "Cinnamon", "Clove", "Paprika", "Nutmeg", "Thyme",
    # Colours
    "Crimson", "Indigo", "Azure", "Cerulean", "Scarlet", "Saffron", "Teal",
    # Cute & wiggly
    "Sprinkles", "Noodle", "Bloop", "Flopper", "Skipper", "Wobble", "Doodle",
    "Fizzy", "Squiggle", "Blip", "Jelly", "Wriggle",
    # Nautical
    "Buoy", "Mast", "Siren", "Keel", "Rudder",
    # Ocean moods
    "Surge", "Cascade", "Eddy", "Crest", "Briny", "Tidal", "Swell",
    # Misc fun
    "Whimsy", "Dazzle", "Twinkle", "Swirl", "Shimmer", "Glisten", "Glitch",
    "Prancer", "Scooter", "Biscotti", "Tofu", "Dumpling", "Ramen",
]

# Names specific to rare species — slightly more dramatic/mysterious.
RARE_NAMES = [
    "Wraith", "Specter", "Glimmer", "Mirage", "Phantom", "Flicker", "Wisp",
    "Eclipse", "Veil", "Prism", "Aura", "Dusk", "Ember", "Zephyr", "Oracle",
    "Nimbus", "Solstice", "Enigma", "Vesper", "Cinder",
]


def by_name(name: str) -> dict | None:
    for s in SPECIES:
        if s["name"] == name:
            return s
    return None


def common_species() -> list[dict]:
    """Return only non-rare, non-uncommon species."""
    return [s for s in SPECIES if not s.get("rare") and not s.get("uncommon")]


def uncommon_species() -> list[dict]:
    """Return uncommon species (more common than rare, less common than common)."""
    return [s for s in SPECIES if s.get("uncommon")]


def rare_species() -> list[dict]:
    """Return rare species (excluding super-rare)."""
    return [s for s in SPECIES if s.get("rare") and not s.get("super_rare")]


def super_rare_species() -> list[dict]:
    """Return super-rare species only."""
    return [s for s in SPECIES if s.get("super_rare")]
