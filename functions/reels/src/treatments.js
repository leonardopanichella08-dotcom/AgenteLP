// Elenco dei trattamenti selezionabili (solo quelli flaggati ✅).
// `id` è stabile: finisce nei percorsi del Blob store, non cambiarlo dopo l'uso.
export const CATEGORIES = [
  {
    id: 'epil',
    label: 'EPILAZIONE',
    items: [
      ['epil-laser-808', 'Laser diodo 808 nm'],
      ['epil-ndyag-1064', 'Laser Nd:YAG 1064 nm'],
      ['epil-ipl', 'IPL (luce pulsata)'],
      ['epil-dinolite', 'Tricoscopio Dino-Lite'],
    ],
  },
  {
    id: 'viso',
    label: 'VISO',
    items: [
      ['viso-facescan', 'FaceScan 3D · MEICET MC88'],
      ['viso-peeling-us', 'Peeling ultrasonico'],
      ['viso-iono-disinc', 'Ionoforesi disincrostante'],
      ['viso-microderm', 'Microdermoabrasione'],
      ['viso-microneedling-rf', 'Microneedling RF + Vacuum'],
      ['viso-led', 'LED (rosso, blu, viola)'],
      ['viso-ndyag-1064', 'Laser Nd:YAG 1064 nm'],
      ['viso-elettroporatore', 'Elettroporatore'],
      ['viso-iface', 'I-FACE i-Motion'],
      ['viso-diatermia', 'Diatermia'],
      ['viso-rf-mono', 'Radiofrequenza Monopolare'],
      ['viso-ossigeno', 'Veicolazione transdermica con ossigeno compresso'],
      ['viso-iono-veic', 'Ionoforesi veicolante'],
    ],
  },
  {
    id: 'corpo',
    label: 'CORPO',
    items: [
      ['corpo-onde-urto-vacuum', "Onde d'urto con vacuum"],
      ['corpo-dren-tone', 'Dren-Tone'],
      ['corpo-onda-urto', "Onda d'urto"],
      ['corpo-endodermico', 'Endodermico'],
      ['corpo-liposculture', 'Liposculture'],
      ['corpo-rf-mono', 'Radiofrequenza monopolare'],
      ['corpo-termosauna', 'Termosauna'],
      ['corpo-crioterapia', 'Crioterapia a placche'],
    ],
  },
];

// Opzione speciale per il materiale da non usare.
export const DISCARD = { id: 'scarta', label: 'Da scartare', folder: '_SCARTATI' };

export const TREATMENTS = new Map();
for (const c of CATEGORIES) {
  for (const [id, label] of c.items) {
    const folder = `${c.label} - ${label}`.replace(/[\\/:*?"<>|]/g, '-');
    TREATMENTS.set(id, { id, label, category: c.label, folder });
  }
}
TREATMENTS.set(DISCARD.id, { ...DISCARD, category: '' });

export const isValidTreatment = (id) => TREATMENTS.has(id);
