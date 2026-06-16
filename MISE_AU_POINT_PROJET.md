# Mise au point du projet

Date: 2026-06-16

## Etat general

Le projet a maintenant un socle Full HD valide et audite. Le lancement HD,
les exports d'images fixes, les frames VQA, les assets CDCACHE et les rapports
`.tex` sont relies par un tableau de bord local.

Point d'entree principal:

```text
output/fullhd_dashboard/index.html
```

Pipeline de validation:

```sh
python3 tools/lolg_fullhd_pipeline.py --mode quick --fail-on-issues
```

Validation actuelle:

```text
Full HD audit: pass
Gates: 229/229
Full HD PNGs: 177452
Dashboard cards: 4
Quick links: 229
```

## Ce qui est stable

- `RUN_HD.sh` est le lanceur HD principal.
- Les reglages de qualite du jeu sont reappliques au lancement.
- Les images fixes PCX sont exportees et verifiees en 1920x1080.
- Les VQA ont un vrai rendu frame par frame exporte en Full HD.
- Les assets CDCACHE ont un pack HD verifie, avec 3104 assets references.
- Le tableau de bord centralise les galeries, manifests, rapports et preuves.
- L'inventaire historique des anciens fichiers projet est integre.

## Compteurs importants

```text
VQA entries: 1955
VQA Full HD frames: 171167
Static Full HD images: 78
Visual MIX entries covered: 1992
CDCACHE HD assets: 3104
.tex-linked assets: 194
.tex material rows in decoder queue: 36
```

Inventaire historique:

```text
Historical project files: 17537
Core historical files: 18
Historical bytes: 4147149127
```

Rapports:

```text
output/project_legacy_inventory/index.html
output/project_legacy_inventory/summary.csv
output/project_legacy_inventory/manifest.csv
```

## VQA

Le decodeur VQA n'est plus seulement exploratoire: il rend des frames natives
et Full HD, y compris le balayage complet des 1955 entrees detectees. Les
sorties all-frames actuelles couvrent 171167 frames Full HD et 13 lignes
`held_frame`, qui correspondent a des frames declarees sans pointeur propre.

Documentation:

```text
VQA_DECODER.md
```

Sorties principales:

```text
output/vqa_batch_window_lcw_transparent0_allframes/index.html
output/vqa_batch_window_lcw_transparent0_allframes/status.html
```

## Textures .tex

Le vrai decodeur `.tex` est le chantier actif. L'etat actuel est proprement
instrumente: les rapports isolent les gaps, les frontieres, les runs, les
tokens, les controles et les cas non resolus. Les promotions automatiques sont
conservatrices: quand une hypothese ne produit pas une regle robuste, elle reste
en revue.

Roadmap de travail:

```text
output/tex_decoder_roadmap/index.html
output/tex_decoder_roadmap/queue.csv
```

Elle classe les 51 decisions du noisy review en pistes actionnables. Etat
actuel: 0 byte promotable automatiquement; la piste dominante reste
`gradient`, puis les familles `mixed_token`, `jump`, `direction_value` et
`flat_walk`.

La premiere reduction de la piste `micro_token` isole les lignes
`jump_mixed_walk`:

```text
output/tex_micro_jump_split/index.html
output/tex_micro_jump_split/buckets.csv
```

Etat courant:

```text
Jump-mixed rows: 66
Jump-mixed bytes: 1680
Review buckets: 48
Repeated buckets: 9
Repeated bucket bytes: 909
Promotion-ready bytes: 0
```

Etat courant du noisy review:

```text
Noisy rows: 150
Noisy bytes: 5149
Promotion-ready bytes: 0
Decision rows: 51
Blocked rows: 51
Issue rows: 0
```

La derniere mise au point `.tex` relie les gradients repetes aux seeds palette,
isole leur famille de decalage, puis verifie les voisinages, phases et etats
source du controle:

```text
Seed rows: 2
Seed bytes: 122
Candidate seed bytes: 122
Copy-unlock bytes: 122
Total potential bytes: 244
Repeated transform-set bytes: 0
Repeated shift-family bytes: 122
Repeated exact shift-set bytes: 0
Distinct shift deltas: 4
Delta mapping rows: 14
Delta mapping bytes: 122
Source-only repeated delta bytes: 0
Target-oracle repeated delta bytes: 86
Source-context repeated delta bytes: 0
Source-context conflicted evidence bytes: 569
Source/control phase selector groups: 902
Source/control phase repeated delta bytes: 0
Source/control phase conflicted evidence bytes: 15425
Source/control state groups: 2013
Source/control state repeated delta bytes: 0
Source/control state conflicted evidence bytes: 31654
Source/control opcode transition groups: 187
Source/control opcode repeated transition bytes: 0
Source/control opcode conflicted evidence bytes: 1220
Source/control opcode offset-reuse bytes: 43
Source/control semantic opcode groups: 89
Source/control semantic opcode repeated bytes: 0
Source/control semantic opcode conflicted evidence bytes: 2004
Promotion-ready bytes: 0
```

Le contexte mixed-jump reste une preuve utile:

```text
Rows: 19
Bytes: 682
Repeated band-pair bytes: 566
Repeated payload bytes: 0
Source >=50% bytes: 0
```

Le contexte direction/value par contexte local reste utile:

```text
Rows: 34
Bytes: 726
Best context: surface+key+head4
Repeated stable bytes: 0
Split-only stable bytes: 726
Promotion-ready bytes: 0
```

Le dernier ajout utile teste la grammaire payload des memes lignes:

```text
Rows: 34
Bytes: 726
Repeated top-token/top-nibble bytes: 565
Dominant JUMP bytes: 593
Repeated transition-profile bytes: 0
Repeated payload bytes: 0
Promotion-ready bytes: 0
```

Le dernier ajout utile compare ces profils aux sources de fixture:

```text
Rows: 34
Bytes: 726
Best segment_gap bytes: 726
Profile overlap >=75% bytes: 251
Exact profile match bytes: 26
Positional >=50% bytes: 52
Repeated source-profile bytes: 0
Promotion-ready bytes: 0
```

Le dernier ajout utile teste les valeurs fixes depuis ces sources:

```text
Rows: 34
Bytes: 726
Transform count: 14
Best exact total: 29
Max exact ratio: 0.200000
Rows >=25%: 0
Exact match bytes: 0
Top transform: xor80 / 232 bytes / 2 exact bytes
Promotion-ready bytes: 0
```

Le dernier ajout utile teste aussi un glissement local autour de ces sources:

```text
Rows: 34
Bytes: 726
Scan radius: 128
Offset candidates: 4512
Best exact total: 95
Max exact ratio: 0.428571
Rows >=25%: 12
Rows >=50%: 0
Exact match bytes: 0
Top transform: add1 / 161 bytes / 22 exact bytes
Promotion-ready bytes: 0
```

Le dernier ajout utile teste le contexte controle autour des memes offsets:

```text
Rows: 34
Bytes: 726
Context radius: 4
Direction signal groups: 11
Repeated direction signal bytes: 618
Repeated direction context bytes: 123
Combined context groups: 34
Repeated combined context bytes: 0
Repeated op-phase bytes: 0
Repeated payload bytes: 0
Promotion-ready bytes: 0
```

Conclusion: il y a des formes repetables et deux seeds plausibles qui
debloquent leurs copies a distance fixe, mais pas encore de signal de payload,
de source, d'alignement local, de transform-set repete ou de contexte controle
assez fort pour promouvoir une nouvelle regle de decodeur.

## Anciennes additions projet

Les anciens fichiers ajoutes au projet ne sont plus perdus dans l'arborescence.
Ils sont classes sans etre deplaces:

```text
tools/lolg_project_legacy_inventory.py
PROJECT_LEGACY_FILES.md
output/project_legacy_inventory/index.html
```

Categories principales:

```text
diagnostic_preview: 8277 files
diagnostic_report: 1464 files
extracted_reference: 3056 files
hd_asset_tree: 3669 files
project_script: 682 files
core_project_file: 18 files
```

## Prochaine passe technique

Priorite 1: continuer le decodeur `.tex` frame/row par frame, mais uniquement
avec des hypotheses qui reduisent les gaps sans faux positifs.

Priorite 2: transformer les meilleurs rapports de gaps en un module decodeur
unique, au lieu d'accumuler seulement des sondes separees. Un premier point de
controle reproductible existe maintenant avec:

```sh
python3 tools/lolg_fullhd_pipeline.py --mode quick --fail-on-issues
python3 tools/lolg_fullhd_pipeline.py --mode reports --dry-run
```

Priorite 3: garder le tableau de bord comme source de verite: toute nouvelle
sonde utile doit produire `summary.csv`, `index.html`, puis etre auditee.

## Validation a relancer apres modification

```sh
python3 tools/lolg_fullhd_pipeline.py --mode quick --fail-on-issues
```

Etat de reference apres cette mise au point:

```text
Audit final: pass
Gates: 229/229
```
