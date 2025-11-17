NOTE_TO_PC = {"C":0,"B#":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"Fb":4,"E#":5,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11,"Cb":11}
PC_TO_SHARP = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
PC_TO_FLAT  = ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"]

def parse_note(n):
    n = n.strip()
    head = ""
    for ch in n:
        if ch.isalpha() or ch in "#b":
            head += ch
        else:
            break
    tail = n[len(head):]
    pc = NOTE_TO_PC[head]
    if tail and (tail.lstrip("-").isdigit()):
        octave = int(tail)
        midi = pc + 12*(octave+1)
    else:
        midi = pc + 12*5
    return pc, midi

def norm_pcset(pcs):
    return tuple(sorted(set([p % 12 for p in pcs])))

# --- Interval naming ---------------------------------------------------------

INTERVAL_NAMES = {
    0:"P1/8",
    1:"m2(♭2)",
    2:"M2",
    3:"m3(♭3)",
    4:"M3",
    5:"P4",
    6:"TT(♯4/♭5)",
    7:"P5",
    8:"m6(♯5)",
    9:"M6",
    10:"m7(♭7)",
    11:"M7",
}

def name_interval(semi):
    return INTERVAL_NAMES[semi % 12]

# --- Chord dictionary (interval sets) ---------------------------------------

CHORD_TEMPLATES = {
    "maj":{0,4,7},"min":{0,3,7},"dim":{0,3,6},"aug":{0,4,8},
    "sus2":{0,2,7},"sus4":{0,5,7},"5":{0,7},
    "6":{0,4,7,9},"m6":{0,3,7,9},"add9":{0,4,7,2},
    "add4":{0,4,7,5},"madd9":{0,3,7,2},
    "maj7":{0,4,7,11},"7":{0,4,7,10},"m7":{0,3,7,10},
    "mMaj7":{0,3,7,11},"ø7":{0,3,6,10},"dim7":{0,3,6,9},
    "+maj7":{0,4,8,11},"+7":{0,4,8,10},
    "9":{0,4,7,10,2},"maj9":{0,4,7,11,2},"m9":{0,3,7,10,2},
    "11":{0,4,7,10,2,5},"m11":{0,3,7,10,2,5},
    "13":{0,4,7,10,2,9},"maj13":{0,4,7,11,2,9},"m13":{0,3,7,10,2,9},
    "7♭5":{0,4,6,10},"7♯5":{0,4,8,10},"7♭9":{0,4,7,10,1},
    "7♯9":{0,4,7,10,3},"7♭13":{0,4,7,10,8},"7alt":{0,4,10}
}
ALT_ALLOWED_FOR_7ALT = {6,8,1,3,8}
SYMBOL_RENDER = {
    "maj":"", "min":"m","dim":"dim","aug":"+","sus2":"sus2","sus4":"sus4","5":"5",
    "6":"6","m6":"m6","add9":"add9","add4":"add4","madd9":"m(add9)",
    "maj7":"maj7","7":"7","m7":"m7","mMaj7":"m(maj7)","ø7":"m7♭5",
    "dim7":"dim7","+maj7":"+maj7","+7":"+7",
    "9":"9","maj9":"maj9","m9":"m9","11":"11","m11":"m11",
    "13":"13","maj13":"maj13","m13":"m13",
    "7♭5":"7♭5","7♯5":"7♯5","7♭9":"7♭9","7♯9":"7♯9","7♭13":"7♭13","7alt":"7alt"
}

def rotate(p, root): #can traverse them not in order
    return {(x - root) % 12 for x in p}

def describe_root(pc, prefer_flats=False): #the standard naming from user preference
    return (PC_TO_FLAT if prefer_flats else PC_TO_SHARP)[pc]

def match_templates(pcs): #If it is a template(regular)
    pcs = set(pcs)
    results = []
    for root in pcs:
        rel = rotate(pcs, root)
        for name, tmpl in CHORD_TEMPLATES.items():
            if name == "7alt":
                if {4,10}.issubset(rel) and (rel & ALT_ALLOWED_FOR_7ALT):
                    results.append((root,name))
                continue
            if rel.issubset(tmpl):
                results.append((root,name))
    seen=set()
    return [(r,n) for r,n in results if not (r,n) in seen and not seen.add((r,n))]

def label_with_bass(chord_labels, midi_notes, pcs, prefer_flats=False):
    if not midi_notes: return []
    bass_midi=min(midi_notes)
    bass_pc=bass_midi%12
    out=[]
    for root,name in chord_labels:
        root_name=describe_root(root,prefer_flats)
        sym=SYMBOL_RENDER.get(name,name)
        base=f"{root_name}{sym}"
        if bass_pc!=root and bass_pc in pcs:
            out.append(f"{base}/{describe_root(bass_pc,prefer_flats)}")
        else:
            out.append(base)
    return sorted(set(out))

# --- NEW: single-label helper and scoring to pick the most sensible chord ---

def _render_single(root, name, midi_notes, pcs, prefer_flats=False):
    """Render exactly one label, respecting slash-bass if applicable."""
    labels = label_with_bass([(root, name)], midi_notes, pcs, prefer_flats)
    return labels[0] if labels else None

def _score_candidate(root, name, pcs_set, midi_notes):
    #Heuristic score: coverage, defining tones, simplicity, bass fit, realism.
    rel = rotate(set(pcs_set), root)
    tmpl = CHORD_TEMPLATES[name]

    coverage = len(rel) / max(1, len(tmpl))

    #encourage 3rd & 7th when the chord quality implies them
    has_third = (4 in rel) or (3 in rel)
    has_seventh = (10 in rel) or (11 in rel)
    miss3 = 0.30 if (name not in ["sus2","sus4","5"] and not has_third) else 0.0
    miss7 = 0.15 if any(k in name for k in ["7","9","11","13"]) and not has_seventh else 0.0

    # slight bias toward simpler names unless 9/11/13/etc.
    complexity = (len(tmpl) - 3) * 0.04
    if any(t in rel for t in (2,5,9)):  # 9/11/13 present
        complexity *= 0.4

    # bass fit 
    bass_bonus = 0.0
    if midi_notes:
        bass_pc = min(midi_notes) % 12
        if bass_pc == root:
            bass_bonus = 0.15
        elif ((4 in rel and bass_pc == (root+4)%12) or
              (3 in rel and bass_pc == (root+3)%12)):
            bass_bonus = 0.05
        elif 7 in rel and bass_pc == (root+7)%12:
            bass_bonus = 0.03

    #if alterations actually present
    realism = 0.0
    if name in ["7alt","7♯5","7♭5","7♯9","7♭9","7♭13"]:
        alts = rel & {6,8,1,3,8}
        realism += 0.08 * len(alts)
        if not alts:
            realism -= 0.10

    # if exactly a clean triad was played, boost it
    triad_bonus = 0.0
    if len(pcs_set) == 3 and rel == tmpl and name in ["maj","min","dim","aug","sus2","sus4"]:
        triad_bonus = 0.12

    return (0.90*coverage) - miss3 - miss7 - complexity + bass_bonus + realism + triad_bonus


def analyze(notes, prefer_flats=False):
    pcs=[]; midis=[]
    for n in notes:
        pc,midi=parse_note(n)
        pcs.append(pc); midis.append(midi)
    pcs_set=norm_pcset(pcs)
    '''named=[describe_root(p,prefer_flats) for p in pcs_set]
    print(f"Input notes: {notes}")
    print(f"Pitch classes: {pcs_set} → {named}")

    if len(pcs_set)==1:
        print(f"Single note: {named[0]}")
        return'''

    if len(pcs_set)==2:
        a,b=sorted(pcs_set)
        print("Intervals:")
        print(f"  {describe_root(a,prefer_flats)}→{describe_root(b,prefer_flats)} : {name_interval((b-a)%12)}")
        print(f"  {describe_root(b,prefer_flats)}→{describe_root(a,prefer_flats)} : {name_interval((a-b)%12)} (inversion)")
        d = (b - a) % 12
        if d in (7,5):  # perfect 5th/4th 
            root = a if d == 7 else b
            label = _render_single(root, "5", midis, set(pcs_set), prefer_flats)
            print("Best chord guess:", label)
        else:
            guess = {3:"minor shell (m3)",4:"major shell (M3)",
                     10:"m7 shell",11:"M7 shell"}.get(d,"ambiguous dyad")
            print("Best chord guess:", guess)
        return

    # 3+ notes: pick the single best by score among all candidates
    candidates=match_templates(pcs_set)
    if not candidates:
        print("No chord.")
        return

    best = max(candidates, key=lambda rc: _score_candidate(rc[0], rc[1], pcs_set, midis))
    best_root, best_name = best
    best_label = _render_single(best_root, best_name, midis, set(pcs_set), prefer_flats)
    print(best_label)

#Test
if __name__=="__main__":
    examples=[
        ["C","E","G","B"],
        ["Db","F","Ab","C"],
        ["C#","E","G","Bb"],
        ["C","Eb","G","Bb","D"],
        ["E","G","C"],  # inversion check
        ["G","C","D"],  # sus/power-like
        ["C", "E", "G", "Ab"]
    ]
    for ex in examples:
        print(ex)
        analyze(ex, prefer_flats=False)  # change to True for flat keys

