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
Historical project files: 17536
Core historical files: 18
Historical bytes: 4147148994
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

La passe de positions montre que les buckets repetes partagent des bins de
sauts, mais pas une signature de positions reusable:

```text
output/tex_micro_jump_positions/index.html
output/tex_micro_jump_positions/buckets.csv
output/tex_micro_jump_positions/targets.csv
```

Etat courant:

```text
Target bytes: 909
Position signature groups: 27
Repeated position signature bytes: 0
Bucket-bin repeat bytes: 909
Promotion-ready bytes: 0
```

La sonde payload pousse le test sur les 9 buckets `jump_mixed` repetes:

```text
output/tex_micro_jump_mixed_payload/index.html
output/tex_micro_jump_mixed_payload/rows.csv
output/tex_micro_jump_mixed_payload/groups.csv
output/tex_micro_jump_mixed_payload/distances.csv
```

Etat courant:

```text
Target bytes: 909
Repeated payload signature bytes: 0
Repeated value histogram bytes: 0
Repeated signed profile bytes: 0
Source profile >=75 bytes: 209
External best exact bytes: 48
Spatial best distance: 1
Spatial best correct bytes: 169 / 875
Spatial exact copy bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les 909 bytes des buckets repetes ne cachent ni payload exact
repete, ni profil signed repete, ni copie spatiale exacte. Les 209 bytes de
profil source eleve restent un indice trop large, car l'exact source plafonne a
48 bytes. La piste `jump_mixed` reste donc une grammaire de sauts a decoder,
pas une promotion par repetition directe.

Le profil direct des 66 lignes `jump_token` generalise ce controle aux classes
`dense_jump_weave`, `mixed_jump_split`, `repeated_nibble_jump`,
`long_island_split` et `sparse_jump_split`:

```text
output/tex_jump_token_payload_profile/index.html
output/tex_jump_token_payload_profile/rows.csv
output/tex_jump_token_payload_profile/groups.csv
output/tex_jump_token_payload_profile/distances.csv
```

Etat courant:

```text
Target bytes: 1680
Dense jump bytes: 601
Mixed jump bytes: 682
Repeated nibble bytes: 231
Repeated payload signature bytes: 0
Class-peer >=50 bytes: 69
Source profile >=75 bytes: 631
External best exact bytes: 166
Spatial best distance: 1
Spatial best correct bytes: 353 / 1619
Spatial exact copy bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les profils source eleves couvrent une partie notable des
`jump_token`, mais aucune signature payload, histogramme ou profil signed ne se
repete, et les distances spatiales restent fausses. Cette piste doit donc
continuer par grammaire de sauts/etat, pas par replay ou source directe.

La passe etat/opcode `jump-token` teste les ancres `control_ref_offset`
disponibles, l'ancre reconstruite via `start_mod64`, les signatures de fenetre
controle, le `control_prefix` et le fragment:

```text
output/tex_jump_token_payload_state_opcode/index.html
output/tex_jump_token_payload_state_opcode/rows.csv
output/tex_jump_token_payload_state_opcode/groups.csv
output/tex_jump_token_payload_state_opcode/candidates.csv
output/tex_jump_token_payload_state_opcode/contexts.csv
```

Etat courant:

```text
Target bytes: 1680
Control anchor rows: 51
Raw exact control/start: 19 / 16
Best byte state: prefix_byte_pos16 46 / 311
Best high state: prefix_byte_pos16 136 / 311
High baseline precision: 0.345833
Source-state rejected: 1
Promotion-ready bytes: 0
```

Conclusion: meme avec 51 ancres controle, les etats locaux ne produisent ni le
byte complet ni un high nibble superieur au biais global. Les `jump-token`
restent donc bloques sur une grammaire de sauts plus haute, pas sur une
promotion via fenetre controle/source locale.

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

Le profil direct des lignes `gradient_like` rassemble les preuves payload,
source et spatiales avant de descendre dans les sous-problemes:

```text
output/tex_gradient_payload_profile/index.html
output/tex_gradient_payload_profile/rows.csv
output/tex_gradient_payload_profile/groups.csv
output/tex_gradient_payload_profile/distances.csv
```

Etat courant:

```text
Target bytes: 1925
Small-delta walk bytes: 452
Flat-run walk bytes: 813
Repeated payload signature bytes: 244
Class-peer >=50 bytes: 395
Source profile >=75 bytes: 701
External best exact bytes: 156
Spatial exact copy bytes: 122
Promotion-ready bytes: 0
```

Conclusion: le profil confirme les deux copies exactes a distance 320 deja
isolees, mais l'exact source direct reste trop faible et les profils source
eleves sont trop larges. Les lignes `gradient_like` restent donc bloquees sur
un decodeur d'etat/opcode, pas sur une source ou copie directe generalisable.

La passe etat/opcode `gradient_like` teste ensuite les ancres
`control_ref_offset`, l'ancre reconstruite via `start_mod64`, les signatures de
fenetre controle, le `control_prefix` et le fragment sans utiliser les classes
payload comme predicteurs:

```text
output/tex_gradient_payload_state_opcode/index.html
output/tex_gradient_payload_state_opcode/rows.csv
output/tex_gradient_payload_state_opcode/groups.csv
output/tex_gradient_payload_state_opcode/candidates.csv
output/tex_gradient_payload_state_opcode/contexts.csv
```

Etat courant:

```text
Target bytes: 1925
Control anchor rows: 32
Raw exact control/start: 27 / 21
Best byte state: prefix_byte_pos16 60 / 252
Best step state: window_head_pos16 187 / 298
High baseline precision: 0.530390
Source-state rejected: 1
Promotion-ready bytes: 0
```

Conclusion: les contextes locaux donnent des indices de bande/forme, mais ils
ne produisent pas le byte complet ni une transition fiable. Les
`gradient_like` doivent donc passer par une grammaire opcode plus haute, pas
par une promotion de fenetre controle/source locale.

La sonde macro-opcode `gradient_like` regroupe ensuite les selecteurs
source-only plus hauts: regle fixture, longueur, classes d'ancre, fenetre
controle, prefixe et fragment. Elle teste ces selecteurs contre le payload
exact, les formes de bande/step et les classes grossieres sans utiliser de
valeur payload comme selecteur:

```text
output/tex_gradient_macro_opcode/index.html
output/tex_gradient_macro_opcode/rows.csv
output/tex_gradient_macro_opcode/groups.csv
output/tex_gradient_macro_opcode/families.csv
```

Etat courant:

```text
Target bytes: 1925
Selector groups: 1392
Deterministic repeated evidence bytes: 11853
Conflicted evidence bytes: 52935
Best macro selector: dominant_delta / fixture_rule_length 845 / 528
Exact payload repeated evidence bytes: 116
Band shape repeated evidence bytes: 398
Step shape repeated evidence bytes: 116
Top nibble repeated evidence bytes: 3616
Promotion-ready bytes: 0
```

Conclusion: les macro-selecteurs expliquent mieux des proprietes grossieres
comme le delta dominant ou le nibble haut, mais les conflits restent massifs et
les preuves payload/forme exactes sont trop faibles. La prochaine passe doit
donc scinder les conflits du selecteur `dominant_delta / fixture_rule_length`
avant toute promotion opcode.

Le split de ces conflits isole les deux groupes `dominant_delta` non resolus
du macro-selecteur et teste des sous-selecteurs source: ancre controle,
fenetre controle, paire ancre/fenetre, modulo controle/depart, longueur exacte
et position d'operation:

```text
output/tex_gradient_macro_conflict_split/index.html
output/tex_gradient_macro_conflict_split/rows.csv
output/tex_gradient_macro_conflict_split/splits.csv
output/tex_gradient_macro_conflict_split/families.csv
```

Etat courant:

```text
Conflict groups: 2
Conflict bytes: 528
Best repeated split: control_anchor_class 280 / 213
Best split singleton bytes: 35
Best split conflict reduction bytes: 315
Lowest conflict split: exact_length 128 / 0 / 400 singleton
Promotion-ready bytes: 0
```

Conclusion: l'ancre controle stabilise 280 bytes repetes et reduit le conflit
restant a 213 bytes, mais le meilleur split sans conflit (`exact_length`)
isole 400 bytes en singletons. La prochaine passe doit donc resoudre le groupe
residuel `mod64=23` par un signal source supplementaire avant promotion.

La sonde residuelle reprend ensuite ce groupe `mod64=23` et separe les
fenetres source locales des bins d'etat/position (`span_index`, `op_index`,
offset decode et longueur):

```text
output/tex_gradient_macro_residual_state/index.html
output/tex_gradient_macro_residual_state/rows.csv
output/tex_gradient_macro_residual_state/groups.csv
output/tex_gradient_macro_residual_state/families.csv
```

Etat courant:

```text
Residual rows: 3
Residual bytes: 213
Best source selector: source_window_signature 0 / 139 / 74 singleton
Best state selector: op_index_band8 138 / 0 / 75 singleton
Best selector: state / op_index_band8
Promotion-ready bytes: 0
```

Conclusion: les fenetres source locales restent conflictuelles, y compris
quand l'ancre de depart est identique. Le meilleur signal vient de la phase
d'operation (`op_index_band8` ou `span_index_band4`), qui stabilise 138 bytes
mais laisse le cas delta=1 en singleton. La prochaine passe doit etendre ces
bins de phase sur toutes les lignes macro gradient avant promotion.

La sonde de phase globale applique ensuite ces bins a toutes les lignes
`gradient_like` macro, en separant les phases pures (`op_index`, `span_index`,
offset, longueur) des phases combinees avec fixture ou ancre:

```text
output/tex_gradient_macro_phase/index.html
output/tex_gradient_macro_phase/rows.csv
output/tex_gradient_macro_phase/groups.csv
output/tex_gradient_macro_phase/families.csv
```

Etat courant:

```text
Target bytes: 1925
Selector families: 24
Best coarse phase: dominant_delta / op_index_band4 1288 / 530
Best payload phase: band_shape / fixture_length_op_phase 0 / 196
Payload deterministic evidence bytes: 0
Promotion-ready bytes: 0
```

Conclusion: le signal de phase se generalise bien pour le delta dominant, avec
`op_index_band4` a 1288 bytes deterministes, mais il conserve 530 bytes
conflictuels et ne predit aucune forme payload repetee. La prochaine passe
doit donc scinder les conflits `op_index` avant toute promotion opcode.

Le split des conflits `op_index_band4` isole ensuite les quatre bins encore
ambigus et teste fixture, longueur, ancres, fenetres controle et phases plus
fines:

```text
output/tex_gradient_macro_phase_conflict_split/index.html
output/tex_gradient_macro_phase_conflict_split/rows.csv
output/tex_gradient_macro_phase_conflict_split/splits.csv
output/tex_gradient_macro_phase_conflict_split/families.csv
```

Etat courant:

```text
Conflict groups: 4
Conflict bytes: 530
Best split: fixture_control_mod 138 / 0 / 392 singleton
Lowest conflict split: fixture_control_mod 138 / 0 / 392 singleton
Promotion-ready bytes: 0
```

Conclusion: `fixture_control_mod` retire le conflit, mais seulement en gardant
138 bytes repetes et en isolant 392 bytes. La phase `op_index` seule n'est
donc pas une grammaire opcode suffisante; il faut elargir la grammaire de phase
avant promotion.

La sonde de sequence locale elargit ensuite la phase avec la position dans la
frontier, les ecarts `op/span/start`, les longueurs voisines et les relations
fixture/controle, sans utiliser les valeurs cible des voisins:

```text
output/tex_gradient_macro_phase_sequence/index.html
output/tex_gradient_macro_phase_sequence/rows.csv
output/tex_gradient_macro_phase_sequence/groups.csv
output/tex_gradient_macro_phase_sequence/families.csv
```

Etat courant:

```text
Target bytes: 1925
Selector families: 24
Best sequence phase: dominant_delta / neighbor_op_gap 936 / 522 / 467 singleton
Lowest conflict sequence: dominant_delta / frontier_op_position 869 / 0 / 1056 singleton
Best payload sequence: band_shape / sequence_signature 26 / 159 / 1740 singleton
Promotion-ready bytes: 0
```

Conclusion: la sequence locale n'ameliore pas le signal global
`op_index_band4` et les variantes sans conflit deviennent trop
singleton-heavy. La prochaine passe doit donc chercher une grammaire de
transition fixture/op plus large que la sequence locale d'une frontier.

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

La passe predictive teste ensuite des contextes courts (`prev1`, `prev2`,
position normalisee, signal et controle) en validation leave-one-row-out:

```text
output/tex_micro_mixed_value_payload_predictor/index.html
output/tex_micro_mixed_value_payload_predictor/candidates.csv
```

Etat courant:

```text
Target bytes: 567
Best byte predictor: prev1_pos16 26/122
Best high predictor: prev1_pos16 165/74
High6 baseline precision: 0.626102
Promotion-ready bytes: 0
```

Conclusion: un contexte gauche/position ne predit pas le byte complet
(beaucoup plus de faux que de corrects). Le high nibble a un signal partiel,
mais il reste proche du biais global `0x6*`. Il faut donc eviter de promouvoir
un predicteur local et chercher une source d'etat plus externe.

La passe source compare enfin les payloads du dominant avec les pools externes
du fixture (`segment_gap`, `control_prefix`, `fragment`) et le replay decode:

```text
output/tex_micro_mixed_value_payload_source_profile/index.html
output/tex_micro_mixed_value_payload_source_profile/rows.csv
output/tex_micro_mixed_value_payload_source_profile/groups.csv
```

Etat courant:

```text
Target bytes: 567
Compressed best exact bytes: 31
Decoded zero-bias bytes: 364
Profile overlap >=75 bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les sources compressees ne donnent qu'un recouvrement exact tres
faible. Le replay decode semble meilleur en exact brut, mais surtout parce que
des zones zero transformees par `xor_prefix` reproduisent le byte dominant; ce
n'est pas une source promotable. La piste suivante doit chercher un etat de
decodeur plus structurel que copie/source locale.

La passe spatiale teste enfin les distances de copie dans l'image attendue,
dont les voisinages courts et les distances proches d'une largeur 320:

```text
output/tex_micro_mixed_value_payload_spatial/index.html
output/tex_micro_mixed_value_payload_spatial/rows.csv
output/tex_micro_mixed_value_payload_spatial/distances.csv
```

Etat courant:

```text
Target bytes: 567
Best aggregate distance: 1
Best aggregate correct bytes: 138
Distance 320 correct bytes: 24
Exact copy bytes: 0
Promotion-ready bytes: 0
```

Conclusion: le voisin gauche donne le meilleur score agrege, mais reste trop
faible et produit 429 faux bytes. Les distances type largeur d'image ne
fournissent pas de copie exploitable non plus. Le dominant `mixed_value` reste
donc bloque sur une grammaire d'etat, pas sur une copie spatiale directe.

La passe etat/opcode teste ensuite des contextes externes non-oracle autour du
signal compresse, du `control_ref_mod64`, du `control_prefix` et du fragment:

```text
output/tex_micro_mixed_value_payload_state_opcode/index.html
output/tex_micro_mixed_value_payload_state_opcode/rows.csv
output/tex_micro_mixed_value_payload_state_opcode/candidates.csv
output/tex_micro_mixed_value_payload_state_opcode/contexts.csv
```

Etat courant:

```text
Target bytes: 567
Raw exact signal/control: 5 / 3
Best byte state: signal_byte_pos16 25 / 144
Best high state: signal_byte_pos16 121 / 100
High baseline precision: 0.626102
Source-state rejected: 1
Promotion-ready bytes: 0
```

Conclusion: les contextes d'etat disponibles autour du flux compresse ne
produisent pas le byte complet, et le meilleur high nibble reste inferieur au
biais global `0x6*`. Le dominant `mixed_value` ne doit donc pas etre promu via
ces etats locaux; il faut chercher une grammaire opcode plus haute ou passer
aux familles `gradient`/`jump-token`.

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
