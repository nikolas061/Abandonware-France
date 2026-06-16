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

Elle classe les 51 decisions du noisy review, plus la preuve stable-walk
`+320`, en pistes actionnables. Etat actuel: 52 decisions, 0 byte promotable
automatiquement; la piste dominante reste `gradient`, puis les familles
`mixed_token`, `jump`, `direction_value`, `flat_walk` et `control`.

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

Le split conservateur par familles micro-token donne maintenant une file plus
propre pour les passes suivantes:

```text
output/tex_micro_token_family_split/index.html
output/tex_micro_token_family_split/families.csv
output/tex_micro_token_family_split/conflicts.csv
```

Etat courant:

```text
Target bytes: 5149
Clean family bytes: 5086
Ambiguous bytes: 63
Existing disagreement bytes: 0
Top family: mixed_value
Promotion-ready bytes: 0
```

Conclusion: les familles `mixed_value`, `jump_mixed`, `flat_plateau` et
`small_delta` couvrent presque toute la piste micro-token sans desaccord avec
la classe existante. Le seul cas ambigu est un `mixed_value` de 63 bytes sans
reference de controle; il doit rester en revue pendant que les familles nettes
sont traitees separement.

La famille dominante `mixed_value` est maintenant redecoupee par nibble haut,
bande de longueur et presence du controle:

```text
output/tex_micro_mixed_value_subfamily/index.html
output/tex_micro_mixed_value_subfamily/subfamilies.csv
output/tex_micro_mixed_value_subfamily/signals.csv
```

Etat courant:

```text
Target bytes: 2142
Clean bytes: 2079
Repeated subfamily bytes: 2079
Dominant subfamily: 0x6|medium|control_known|strong
Ambiguous bytes: 63
Promotion-ready bytes: 0
```

Conclusion: les bytes propres de `mixed_value` tombent tous dans des
sous-familles repetees; le cas faible reste le meme `0x6|medium|control_missing`
de 63 bytes. La prochaine passe peut donc attaquer le dominant
`0x6|medium|control_known|strong` separement du reste.

La sous-famille dominante `0x6|medium|control_known|strong` est maintenant
croisee avec les signaux de controle connus:

```text
output/tex_micro_mixed_value_dominant_control/index.html
output/tex_micro_mixed_value_dominant_control/groups.csv
output/tex_micro_mixed_value_dominant_control/rows.csv
```

Etat courant:

```text
Target bytes: 567
Repeated signal bytes: 417
Repeated control+signal bytes: 292
Repeated payload bytes: 0
Dominant control+signal: 27|signed_delta:segment_gap:signed_delta
Promotion-ready bytes: 0
```

Conclusion: le controle stabilise une partie du dominant `mixed_value`
(292 bytes sur un couple controle+signal repete), mais les signatures de
payload et les contextes d'offset restent tous uniques. Cette piste devient
une bonne separation de revue, pas encore une grammaire promotable.

La passe locale sur les payloads du dominant `mixed_value` mesure maintenant
les valeurs et n-grammes internes, au lieu de s'arreter au hash de ligne:

```text
output/tex_micro_mixed_value_payload_local_grammar/index.html
output/tex_micro_mixed_value_payload_local_grammar/rows.csv
output/tex_micro_mixed_value_payload_local_grammar/ngrams.csv
```

Etat courant:

```text
Target bytes: 567
Repeated byte-value bytes: 562
Byte trigram repeated slots: 230
Byte ngram8 repeated slots: 0
High ngram8 repeated slots: 421
Promotion-ready bytes: 0
```

Conclusion: le payload dominant n'est pas aleatoire; les valeurs et motifs
courts se repetent fortement. En revanche, aucune forme complete, aucun payload
et aucun n-gramme byte de longueur 8 ne se repete. La prochaine passe doit donc
chercher une grammaire positionnelle/courte ou un etat externe, pas une copie
longue directe.

La passe suivante analyse les positions normalisees des sauts dans les buckets
repetees:

```text
output/tex_micro_jump_positions/index.html
output/tex_micro_jump_positions/buckets.csv
```

Etat courant:

```text
Position targets: 27
Target bytes: 909
Repeated position signature bytes: 0
Rows with repeated bucket bins: 27
Bytes with repeated bucket bins: 909
Promotion-ready bytes: 0
```

Conclusion: les buckets repetes partagent des zones de sauts, mais pas de
signature exacte stable. La piste reste utile pour separer les familles, pas
pour promouvoir une regle de replay.

La passe complementaire compare les marches micro-token non jump stables
(`plateau_walk`, `banded_small_signed_walk`, `small_signed_walk`):

```text
output/tex_micro_stable_walks/index.html
output/tex_micro_stable_walks/groups.csv
```

Etat courant:

```text
Stable rows: 28
Stable bytes: 1327
Repeated signature groups: 2
Repeated signature bytes: 244
Exact repeat bytes: 244
Distance +320 copy bytes: 122
Promotion-ready bytes: 0
```

Conclusion: deux signatures `plateau_walk` se repetent exactement a +320 bytes.
C'est un bon indice de copie interne, mais pas encore une regle promotable tant
que la source initiale et le controle associe ne sont pas expliques.

Le probe de backrefs sur ces signatures confirme le blocage:

```text
output/tex_micro_stable_backrefs/index.html
output/tex_micro_stable_backrefs/by_distance.csv
```

Etat courant:

```text
Repeated target bytes: 244
Exact copy bytes: 122
Distance +320 exact bytes: 122
Distance +320 known-source bytes: 0
Promotion-ready bytes: 0
```

Conclusion: la distance 320 est la meilleure explication locale, mais les
sources `67..131` et `349..407` ne sont pas encore marquees comme connues par
le replay. La prochaine etape est donc de decoder ces sources, pas de promouvoir
une copie +320 globale.

La sonde suivante attaque directement ces deux sources non connues:

```text
output/tex_micro_stable_sources/index.html
output/tex_micro_stable_sources/sources.csv
```

Etat courant:

```text
Source rows: 2
Source bytes: 122
Full source matches: 0
Best exact bytes total: 16
Known-source bytes before probe: 0
Promotion-ready bytes: 0
```

Conclusion: les sources de la copie +320 ne sont pas des fenetres brutes de
`segment_gap`, `control_prefix` ou `fragment`, ni une transformation simple de
ces fenetres. Elles sont elles-memes encodees et doivent etre traitees comme
un sous-probleme de grammaire, pas comme une source disponible.

La grammaire des runs attendus de ces sources est maintenant caracterisee:

```text
output/tex_micro_stable_source_grammar/index.html
output/tex_micro_stable_source_grammar/runs.csv
```

Etat courant:

```text
Run rows: 35
Run bytes: 122
Local value-hit bytes: 116
Local len/value pair bytes: 23
Local value/len pair bytes: 6
Local literal-run bytes: 20
Promotion-ready bytes: 0
```

Conclusion: les valeurs de palette sont presque toutes presentes dans le flux
local, mais les couples longueur/valeur et les runs litteraux ne couvrent qu'une
minorite des bytes. La prochaine piste est donc un decodeur a etat/opcode sur
ces valeurs locales, pas un simple RLE litteral.

Le contexte local des valeurs presentes est groupe pour chercher un motif
d'opcode reutilisable:

```text
output/tex_micro_stable_value_context/index.html
output/tex_micro_stable_value_context/groups.csv
```

Etat courant:

```text
Value-hit rows: 34
Value-hit bytes: 116
Context groups: 16
Repeated context bytes: 81
Repeated value/length context bytes: 32
Repeated shape bytes: 81
Repeated value/length shape bytes: 32
Promotion-ready bytes: 0
```

Conclusion: plusieurs contextes se repetent, surtout par valeur, mais le couple
valeur/longueur reste trop peu stable pour promouvoir une regle. La
normalisation de forme ne regroupe pas plus large que l'hex exact sur cette
fenetre, donc cette piste sert surtout a ordonner le prochain travail
d'opcode/state-machine.

Le probe table-driven contexte -> run complet mesure ce qui serait directement
predictible:

```text
output/tex_micro_stable_context_rules/index.html
output/tex_micro_stable_context_rules/rules.csv
```

Etat courant:

```text
Context rows: 34
Context bytes: 116
Rule rows: 132
Deterministic exact-context bytes: 10
Deterministic shape bytes: 10
Conflicted rule bytes: 284
Promotion-ready bytes: 0
```

Conclusion: deux petits contextes repetes predisent bien un couple
valeur/longueur, mais la couverture reelle reste trop faible face aux conflits.
Il faut donc continuer vers un modele d'opcodes/etat plus riche avant toute
promotion.

La sonde de transitions entre runs teste si l'etat precedent stabilise le run
suivant:

```text
output/tex_micro_stable_sequences/index.html
output/tex_micro_stable_sequences/rules.csv
```

Etat courant:

```text
Transition rows: 32
Transition bytes: 104
Deterministic next-pair bytes: 16
Deterministic shape-step bytes: 6
Deterministic value-step bytes: 6
Best rule family: shape_offset_step
Promotion-ready bytes: 0
```

Conclusion: l'etat precedent aide a isoler un motif `6a -> 6b` avec step 128,
mais la couverture reste marginale. Cette piste confirme qu'il faut capturer un
etat plus riche que le contexte immediat.

La segmentation par alternance de valeurs de palette isole une sous-zone
repetitive:

```text
output/tex_micro_stable_alternation/index.html
output/tex_micro_stable_alternation/segments.csv
```

Etat courant:

```text
Run bytes: 122
Alternating segment bytes: 68
Longest alternating bytes: 23
Longest values: 0x6c;0x6d
Suffix alternating bytes: 23
Promotion-ready bytes: 0
```

Conclusion: la source 22 contient un suffixe alterne `6c/6d` de 23 bytes. C'est
une bonne cible pour un decodeur specialise de suffixe, mais le prefixe de la
source et la source 18 restent hors couverture.

Le replay specialise de ces segments alternes confirme la reconstruction quand
la sequence de longueurs est connue:

```text
output/tex_micro_stable_alternation_replay/index.html
output/tex_micro_stable_alternation_replay/replays.csv
```

Etat courant:

```text
Segment bytes: 68
Oracle exact bytes: 55
Length local-hit bytes: 63
Alternating suffix bytes: 23
Promotion-ready bytes: 0
```

Conclusion: le suffixe alterne `6c/6d` est reconstruit exactement avec les
longueurs attendues, et ses longueurs ont une evidence locale. Il manque encore
la lecture fiable de cette sequence de longueurs depuis le flux, donc la regle
reste en revue.

La recherche de la sequence de longueurs dans le flux local reduit cet oracle:

```text
output/tex_micro_stable_length_sequences/index.html
output/tex_micro_stable_length_sequences/sequences.csv
```

Etat courant:

```text
Segment bytes: 68
Ordered sequence bytes: 52
Compact sequence bytes: 0
Unique ordered sequence bytes: 0
Multi-segment selector bytes: 0
Suffix ordered bytes: 23
Suffix compact bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les longueurs du suffixe alterne apparaissent bien dans le flux en
ordre, mais elles sont dispersees et non uniques. Les selecteurs simples
testes (`delta`, `mod16`, `mod64`, sequence relative) ne generalisent pas entre
segments: les repetitions observees sont seulement intra-segment. La prochaine
etape est donc de chercher un selecteur d'offsets lie au controle/opcode, pas
seulement aux positions des bytes de longueur.

La comparaison des pools de controle confirme que le controle court n'est pas
la source directe des longueurs:

```text
output/tex_micro_stable_length_control/index.html
output/tex_micro_stable_length_control/pools.csv
```

Etat courant:

```text
Segment bytes: 68
Ordered pool bytes: 52
Compact pool bytes: 0
Best pool: segment_gap
Suffix best pool: segment_gap
Suffix best span: 482
Suffix best gap total: 471
Promotion-ready bytes: 0
```

Conclusion: `control_prefix` et `fragment` ne donnent pas de sequence de
longueurs; tout le signal reste dans le grand `segment_gap`, tres disperse.
La recherche doit donc porter sur une grammaire d'opcodes du `segment_gap` lui
meme.

Le voisinage local des bytes de longueur ne donne pas non plus un opcode de run
direct:

```text
output/tex_micro_stable_length_opcode/index.html
output/tex_micro_stable_length_opcode/candidates.csv
output/tex_micro_stable_length_opcode/context_groups.csv
```

Etat courant:

```text
Candidate bytes: 52
Direct after bytes: 0
Direct before bytes: 0
Nearby value-run bytes: 0
Repeated context bytes: 20
Promotion-ready bytes: 0
```

Conclusion: les bytes de longueur ordonnes ne pilotent pas directement les
valeurs attendues dans leur voisinage court. Les deux contextes repetes
observes sont conflictuels: les memes offsets servent a expliquer des valeurs
differentes selon le segment. Il faut donc chercher un decodeur d'etat plus
large que le voisinage immediat longueur/valeur.

L'analyse des intervalles entre longueurs candidates confirme que les sauts ne
forment pas encore une signature d'etat reutilisable:

```text
output/tex_micro_stable_length_interval/index.html
output/tex_micro_stable_length_interval/transitions.csv
output/tex_micro_stable_length_interval/offset_groups.csv
```

Etat courant:

```text
Transition bytes: 42
Compact transition bytes: 14
Marker transition bytes: 34
Stable signature bytes: 0
Conflicted offset bytes: 20
Promotion-ready bytes: 0
```

Conclusion: les intervalles contiennent bien des marqueurs (`fc`, `00`, `20`,
etc.), mais aucune signature repetee stable. Les seuls offsets reutilises
(`822`, `1108`) sont conflictuels entre segments, ce qui confirme qu'un offset
brut du `segment_gap` ne suffit pas a decrire la transition.

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
