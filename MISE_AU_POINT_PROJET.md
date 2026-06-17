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

La sonde de transition fixture/op decompose ensuite les fixtures macro en
regle, paire `op0/op1`, nibbles, delta, ordre, skip, phase et voisinage:

```text
output/tex_gradient_macro_fixture_transition/index.html
output/tex_gradient_macro_fixture_transition/rows.csv
output/tex_gradient_macro_fixture_transition/groups.csv
output/tex_gradient_macro_fixture_transition/families.csv
```

Etat courant:

```text
Target bytes: 1925
Selector families: 26
Best fixture transition: dominant_delta / fixture_rule_delta_skip 781 / 908 / 236 singleton
Lowest conflict transition: dominant_delta / fixture_rule_delta_phase 778 / 0 / 1147 singleton
Best payload transition: band_shape / fixture_opcode_lo_pair 94 / 1452 / 379 singleton
Promotion-ready bytes: 0
```

Conclusion: les opcodes de fixture expliquent quelques sous-cas repetes, mais
le meilleur signal utile reste soit conflictuel, soit trop singleton-heavy. La
prochaine passe doit donc chercher des clusters d'etat macro cross-frontier
plutot qu'une transition locale fixture/op.

La sonde de clusters d'etat macro teste ensuite les combinaisons cross-frontier
de longueur, skip fixture, phase `op`, controle, ancre de depart et contexte de
frontier:

```text
output/tex_gradient_macro_state_cluster/index.html
output/tex_gradient_macro_state_cluster/rows.csv
output/tex_gradient_macro_state_cluster/groups.csv
output/tex_gradient_macro_state_cluster/families.csv
```

Etat courant:

```text
Target bytes: 1925
Selector families: 30
Best macro cluster: dominant_delta / fixture_rule_length 1490 / 263 / 172 singleton
Lowest conflict cluster: dominant_delta / fixture_skip_phase8 1404 / 0 / 521 singleton
Best payload cluster: band_shape / fixture_rule_skip_length 257 / 1195 / 473 singleton
Length baseline: 1526 / 301 / 98 singleton
Promotion-ready bytes: 0
```

Conclusion: `fixture_skip_phase8` isole un vrai cluster sans conflit pour le
delta dominant, mais il ne fournit pas encore la forme payload. La prochaine
passe doit donc sonder le payload a l'interieur des clusters `skip/op8` avant
toute promotion.

La sonde payload des clusters `skip/op8` ne garde que les groupes repetes et
deterministes en delta, puis teste payload exact, formes `band/step`, nibble
haut et classe:

```text
output/tex_gradient_macro_state_cluster_payload/index.html
output/tex_gradient_macro_state_cluster_payload/rows.csv
output/tex_gradient_macro_state_cluster_payload/groups.csv
output/tex_gradient_macro_state_cluster_payload/families.csv
```

Etat courant:

```text
Target bytes: 1404
Cluster groups: 9
Best payload: band_shape / cluster_rule_length 94 / 125 / 1185 singleton
Exact payload deterministic bytes: 0
Best coarse: gradient_class / cluster_hi 524 / 0 / 880 singleton
Promotion-ready bytes: 0
```

Conclusion: le cluster `skip/op8` est utile pour le delta, mais le payload exact
ne se repete pas. La prochaine passe doit inspecter les transformations de
fenetre/source a l'interieur de ces clusters plutot qu'une promotion par
signature payload.

La sonde source-window des clusters `skip/op8` croise ensuite ces memes lignes
avec les compteurs de `tex_gradient_payload_state_opcode`:

```text
output/tex_gradient_macro_state_cluster_source/index.html
output/tex_gradient_macro_state_cluster_source/rows.csv
output/tex_gradient_macro_state_cluster_source/groups.csv
output/tex_gradient_macro_state_cluster_source/families.csv
```

Etat courant:

```text
Target bytes: 1404
Cluster groups: 9
Control raw exact bytes: 15
Start raw exact bytes: 13
Control high exact bytes: 102
Start high exact bytes: 107
Linear exact bytes: 194
Promotion-ready bytes: 0
```

Conclusion: les fenetres controle/depart donnent seulement un faible signal de
nibble haut et presque aucun replay raw. La prochaine passe doit donc chercher
une transformation litterale/geometrique dans les clusters `skip/op8`, pas une
copie directe de fenetre source.

La sonde litterale/geometrique des clusters `skip/op8` teste ensuite les pools
source (`segment_gap`, `control_prefix`, `fragment`, `decoded_replay`) avec des
transformations simples, puis les copies spatiales avant/arriere jusqu'a 700
pixels:

```text
output/tex_gradient_macro_state_cluster_literal/index.html
output/tex_gradient_macro_state_cluster_literal/rows.csv
output/tex_gradient_macro_state_cluster_literal/sources.csv
output/tex_gradient_macro_state_cluster_literal/distances.csv
```

Etat courant:

```text
Target bytes: 1404
Best source total: 93 / 1404
Best spatial: fwd 1 identity 608 / 1338, exact rows 0
Back distance 320: 188 / 540, exact rows 1
Promotion-ready bytes: 0
```

Conclusion: les transformations litterales et la geometrie large ne donnent pas
de regle promotable. La seule piste concrete est d'isoler la ligne exacte a
distance -320, puis de verifier si elle cache une sous-classe stricte.

La sonde backref des clusters macro-state elargit ce cas a toutes les lignes du
cluster et recherche une source de meme longueur situee exactement 320 bytes
avant:

```text
output/tex_gradient_macro_state_cluster_backref/index.html
output/tex_gradient_macro_state_cluster_backref/pairs.csv
output/tex_gradient_macro_state_cluster_backref/rules.csv
```

Etat courant:

```text
Back320 same-length rows: 4
Exact back320 bytes: 122
False back320 bytes: 175
Best rule: same_length_back320_flat_walk exact=122 false=0
Literal target exact bytes: 64
Promotion-ready bytes: 0
```

Conclusion: le cas exact `dinodead.pcx` fait partie d'une petite sous-classe
`flat_run_walk` a copie verticale -320. Le signal est propre dans ces clusters,
mais trop etroit pour une promotion: il faut maintenant tester cette grammaire
`flat_run_walk` hors des clusters macro-state.

Le rapport large `flat_walk_backref` couvre deja cette extension:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/targets.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/rule_candidates.csv
```

Etat courant:

```text
Flat-walk targets: 17 / 813 bytes
Exact copy bytes: 122
Known-source exact bytes: 0
Unresolved-source exact bytes: 122
Best distance: 320
Best rule false bytes: 267
```

Conclusion: l'elargissement confirme les 122 bytes exacts a distance -320,
mais aucune source n'est encore connue par le replay actuel. La prochaine etape
doit decoder les premieres occurrences `flat_walk` ou leur source de palette
avant toute promotion de copie verticale.

Les rapports de chaine palette montrent pourquoi ces premieres occurrences ne
sont pas encore promotables:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe/index.html
```

Etat courant:

```text
Source candidate bytes: 122
Any source chain bytes: 244
Repeated group chain bytes: 0
Blocked chain bytes: 244
Copy-distance-320 context rows: 2
Shared context rows: 0
Same transform-set rows: 0
Best unique-control overlap: 5
```

Conclusion: les producteurs palette existent pour les deux sources, mais restent
singleton et changent de contexte. La prochaine sonde doit normaliser les
contextes/transformations palette autour des premieres occurrences `flat_walk`.

La sonde de normalisation compare ensuite les paires de signatures repetees et
cherche un delta uniforme de transform ou d'offset entre source et copie:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_normalized_context_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_normalized_context_probe/groups.csv
```

Etat courant:

```text
Repeated signature groups: 2
Matched palette values: 14
Uniform transform delta groups: 0
Uniform offset delta groups: 0
Best transform delta value hits: 6
Promotion-ready bytes: 0
```

Conclusion: la normalisation globale par signature ne suffit pas. Il faut
maintenant descendre au niveau des valeurs palette individuelles dans les deux
signatures repetees.

La sonde par valeur palette separe enfin les deltas transform/offset de chaque
valeur partagee entre source et copie:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/values.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/by_delta.csv
```

Etat courant:

```text
Palette value rows: 14
Best transform delta: -1 / 8 values
Best delta pair: shift=-1|offset=-6 / 4 values
Transform delta groups: 4
Delta pair groups: 10
Promotion-ready bytes: 0
```

Conclusion: le delta par valeur donne une piste, mais reste trop fragmente. La
prochaine passe doit chercher une table compacte valeur->delta, ou un selecteur
plus proche du flux compresse, avant toute promotion.

La table valeur->delta verifie ensuite si les memes valeurs palette conservent
un delta stable entre les deux signatures:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_table_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_table_probe/values.csv
```

Etat courant:

```text
Multi-signature values: 5
Stable transform multi-values: 2
Conflicted transform multi-values: 3
Stable offset multi-values: 1
Stable pair multi-values: 0
Promotion-ready bytes: 0
```

Conclusion: seules `0x6a` et `0x6b` gardent un delta transform stable. Les
valeurs `0x6c`, `0x6d` et `0xaa` restent conflictuelles et doivent etre reliees
a un selecteur du flux compresse.

La sonde des selecteurs compresses relie ensuite ces lignes valeur->delta aux
octets bruts, aux contextes voisins et aux offsets/pools de la source et de la
copie:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe/rows.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe/selectors.csv
```

Etat courant:

```text
Conflicted value rows: 6
Compressed feature groups: 103
Multirow compressed feature groups: 62
Exact transform compressed groups: 15
Exact pair compressed groups: 10
Best transform selector: raw_delta_signed=-1 / 3 rows -> 1
Best pair selector: raw_pair=0x6d->0x6e / 2 rows
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les octets du flux compresse expliquent une partie du conflit
(`raw_delta_signed=-1` couvre les trois conflits a delta transform `+1`, et
`raw_pair=0x6d->0x6e` fixe deux lignes). Il faut maintenant combiner plusieurs
features compressees pour couvrir les six lignes conflictuelles avant toute
promotion.

La sonde de combinaisons teste ensuite les ensembles de features compressees
de taille 1 a 3, en mesurant separement la couverture exacte et le risque de
singletons:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe/feature_sets.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe/groups.csv
```

Etat courant:

```text
Tested feature sets: 1350
Full transform cover sets: 741
Full pair cover sets: 723
Best transform feature set: raw_delta_signed / 6 conflicts
Best transform multirow conflicts: 5
Best transform singleton conflicts: 1
Best pair feature set: raw_pair / 6 conflicts
Best pair multirow conflicts: 1
Best pair singleton conflicts: 5
Promotion-ready bytes: 0
```

Conclusion: `raw_delta_signed` generalise deja le delta transform sur les six
lignes conflictuelles. La paire complete est aussi couverte par `raw_pair`, mais
elle est trop dependante de singletons: 5 conflits sur 6 seraient appris comme
cas uniques. La prochaine passe doit generaliser ces `raw_pair` en familles
d'offsets avant promotion.

La sonde formule remplace ensuite l'apprentissage par paire brute par deux
relations arithmetiques directes:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe/rows.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe/groups.csv
```

Etat courant:

```text
Raw-delta groups: 4
Transform formula exact rows: 14 / 14
Transform formula exact conflicted rows: 6 / 6
Offset formula exact rows: 14 / 14
Offset formula exact conflicted rows: 6 / 6
Pair formula exact rows: 14 / 14
Pair formula exact conflicted rows: 6 / 6
Pair formula mismatch rows: 0
Promotion-ready bytes: 0
```

Conclusion: sur ce corpus, `transform_delta = -raw_delta_signed` resout les
conflits sans table `raw_pair`, et `offset_delta = copy_offset - source_offset`
reconstruit la paire exacte. La prochaine passe doit valider cette formule sur
un corpus flat-walk palette plus large avant de convertir en promotion.

La validation corpus reprend enfin tous les `candidate_plan` produits par
`palette_mix`, pas seulement les paires de signatures repetees. Pour chaque
valeur du plan, elle relit l'octet brut du pool compresse et verifie directement
`plan_shift = signed_delta(raw_byte, value)`:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe/rows.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe/groups.csv
```

Etat courant:

```text
Target rows: 17
Candidate target rows: 7
Value rows: 49
Known multi-signature value rows: 28
Known conflicted value rows: 17
Candidate pools: 2
Transform sets: 7
Shift formula exact rows: 49 / 49
Shift formula exact known-multi rows: 28 / 28
Shift formula exact conflicted rows: 17 / 17
Shift formula mismatch rows: 0
Missing raw rows: 0
Promotion-ready bytes: 0
```

Conclusion: la formule se generalise sur tout le corpus actuellement couvert
par un plan candidat, y compris `control_window`, `control_prefix`, les 7
ensembles de transforms et les 17 occurrences de valeurs conflictuelles connues.
La prochaine passe peut preparer une promotion candidate limitee aux lignes
palette qui ont deja un `candidate_plan`.

La sonde de promotion candidate regroupe ensuite les valeurs exactes par cible
`palette_mix` et produit une liste de cibles pretes a rejouer. Elle ne marque
pas encore de `promotion_ready_bytes`, car aucun replay garde n'a applique la
formule dans un masque de decodeur:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe/targets.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe/values.csv
```

Etat courant:

```text
Candidate target rows: 7
Formula value rows: 49
Formula exact value rows: 49
Known conflicted value rows: 17
Candidate-ready target rows: 7
Candidate-ready bytes: 361
Backref unlock bytes: 122
Unique backref unlock bytes: 0
Backref candidate overlap bytes: 122
Raw candidate plus unlock bytes: 483
Total candidate plus unlock bytes: 361
Candidate pools: 2
Transform sets: 7
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les 7 cibles `candidate_plan` sont pretes pour un replay garde de
la formule palette. Le gain direct attendu est 361 octets. Les 122 octets de
backrefs deja reliees sont un potentiel brut, mais ils recouvrent deux cibles
qui ont elles-memes un `candidate_plan`, donc ils ne forment pas un gain unique
additionnel.

Le replay garde reconstruit ensuite les octets depuis les formes de runs et la
palette unique, puis les applique au-dessus de `tiny_nonzero_fill` seulement si
les masques connus/refuses le permettent:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/fixtures.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/promotions.csv
```

Etat courant:

```text
Fixture rows: 32
Target rows: 7
Replayed target rows: 7
Formula-added bytes: 361
Formula-exact bytes: 361
Formula-false bytes: 0
Skipped known bytes: 0
Skipped rejected bytes: 0
Total clean bytes: 9753
Remaining unresolved bytes: 7693
Issue rows: 0
```

Conclusion: la promotion directe des cibles palette formula est effective et
false-free. Les deux backrefs distance 320 reliees sont deja couvertes par les
candidats directs (`67-131 -> 387-451` et `349-407 -> 669-727`), donc aucun
octet supplementaire n'est a rejouer pour cette chaine.

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

La passe de combinaisons teste ensuite 1561 jeux de features locales (jusqu'a
3 features parmi contexte gauche, position, signal, controle, longueur et
dominante de ligne):

```text
output/tex_micro_mixed_value_payload_combo/index.html
output/tex_micro_mixed_value_payload_combo/candidates.csv
```

Etat courant:

```text
Target bytes: 567
Feature sets: 1561
Candidate rows: 4683
Best byte combo: pos8+pos16+dominant_byte 38/174
Best high combo: prev1+pos16 165/74
False-free byte slots: 0
Best false-free high slots: 4
Promotion-ready bytes: 0
```

Conclusion: meme en combinant les features locales, aucun predicteur full-byte
false-free n'apparait. Le seul signal sans faux reste un indice de nibble haut
tres clairseme (4 slots), insuffisant pour une promotion. La suite doit donc
chercher un etat externe ou un resolveur bas-nibble, pas empiler davantage de
contextes locaux.

La passe high/low isole ces 4 slots high-nibble false-free et teste les
contextes low-nibble sur ce sous-ensemble:

```text
output/tex_micro_mixed_value_payload_high_low/index.html
output/tex_micro_mixed_value_payload_high_low/rows.csv
output/tex_micro_mixed_value_payload_high_low/contexts.csv
```

Etat courant:

```text
High feature set: prev_delta+control
Selected high slots: 4
Selected high rows: 2
Selected low values: f:2|e:1|c:1
Best low resolver: offset_context 0/0, unknown 4
Deterministic low slots: 12
Promotion-ready bytes: 0
```

Conclusion: les contextes low deterministes sont intra-ligne ou singleton; en
validation leave-one-row-out, aucun slot low n'est predit. La piste high locale
est donc trop clairsemee et doit etre ecartee au profit d'une source byte
externe.

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

La passe external-source combo reutilise ensuite les offsets `best`,
`compressed` et `profile` de la sonde source, puis teste les bytes/high/low et
deltas voisins en validation leave-one-row-out:

```text
output/tex_micro_mixed_value_payload_external_source_combo/index.html
output/tex_micro_mixed_value_payload_external_source_combo/candidates.csv
```

Etat courant:

```text
Target bytes: 567
Feature sets: 2211
Candidate rows: 6633
Best byte source combo: profile_b0+prev1 27/106
Best false-free byte slots: 2
Best false-free byte unknown slots: 565
Best false-free high feature set: best_pool+best_d2
Best false-free high slots: 14
Best false-free high unknown slots: 553
Promotion-ready bytes: 0
```

Conclusion: la source externe simple donne un meilleur indice high-nibble que
les contextes locaux (14 slots false-free), mais le byte complet reste trop
clairseme (2 slots seulement). La prochaine passe doit inspecter le low-nibble
de ces 14 slots externes avant toute promotion.

La passe external high/low isole ces 14 slots high-nibble, puis teste les
resolvers low-nibble sur les memes sources externes en validation
leave-one-row-out:

```text
output/tex_micro_mixed_value_payload_external_high_low/index.html
output/tex_micro_mixed_value_payload_external_high_low/rows.csv
output/tex_micro_mixed_value_payload_external_high_low/candidates.csv
```

Etat courant:

```text
High feature set: best_pool+best_d2
Selected high slots: 14
Selected low values: a:3|d:2|9:2|c:2|5:1|f:1|8:1|b:1|e:1
Low feature sets: 377
Best low resolver: best_b2+profile_b1 0/2, unknown 12
False-free low slots: 0
Promotion-ready bytes: 0
```

Conclusion: le signal high externe ne suffit pas a reconstruire le byte. Le
meilleur resolver low ne produit aucun vrai positif en LOO, et aucune
combinaison low false-free n'est disponible. Cette branche est donc rejetee
avant promotion; la suite doit chercher un etat de byte plus riche.

La passe state/external combo croise ensuite les meilleurs signaux d'etat
opcode (`signal_*`, `prefix_*`, `fragment_*`) avec les sources externes et les
features locales (`pos8`, `pos16`, `step`):

```text
output/tex_micro_mixed_value_payload_state_external_combo/index.html
output/tex_micro_mixed_value_payload_state_external_combo/candidates.csv
```

Etat courant:

```text
Feature sets: 3627
Candidate rows: 10881
Best byte state/external combo: signal_byte+fragment_byte+best_pool 33/140
Best false-free byte slots: 0
Best high state/external combo: prefix_high+pos16+step 182/69
Best false-free high feature set: fragment_class+best_pool+best_d2
Best false-free high slots: 14
Promotion-ready bytes: 0
```

Conclusion: le croisement etat/source ameliore le high-nibble global mais ne
donne aucun resolver byte complet. Les meilleurs bytes restent massivement
faux et les 14 slots high false-free retombent sur la meme limite que la
passe high/low externe. La suite doit quitter les combos statiques et chercher
un etat sequentiel du flux.

La passe sequence-state teste ensuite les octets precedents, les deltas
precedents, la forme locale du flux et les longueurs de run:

```text
output/tex_micro_mixed_value_payload_sequence_state/index.html
output/tex_micro_mixed_value_payload_sequence_state/candidates.csv
output/tex_micro_mixed_value_payload_sequence_state/selected_rows.csv
output/tex_micro_mixed_value_payload_sequence_state/selected_low_candidates.csv
```

Etat courant:

```text
Feature sets: 1498
Candidate rows: 5992
Best byte sequence state: prev1+pos4+pos16 33/125
Best false-free byte slots: 0
Best false-free high feature set: prev_delta_bucket+prev_shape+run_len_bucket
Best false-free high slots: 22
Selected low values: f:6|e:4|d:3|8:3|b:3|7:2|9:1
Best selected low resolver: prev2+prev1_high+pos4 3/2, unknown 17
Best false-free selected low resolver: signal+dominant 2, unknown 20
Promotion-candidate bytes: 2
Promotion-ready bytes: 0
```

Conclusion: l'etat sequentiel produit un petit signal high/low, mais il reste
trop rare pour une promotion automatique. Les 2 bytes candidats doivent etre
revus avec traces avant d'entrer dans un replay garde.

La revue des candidats sequence verifie ensuite si les 2 bytes high/low
peuvent etre reproduits par le replay actuel, sans oracle sur les bytes
precedents:

```text
output/tex_micro_mixed_value_payload_sequence_candidate_review/index.html
output/tex_micro_mixed_value_payload_sequence_candidate_review/rows.csv
```

Etat courant:

```text
Candidate bytes: 2
Predicted bytes: 6e:2
Correct/false oracle bytes: 2/0
Known prerequisites: 0/4
Oracle dependency bytes: 2
Replay-ready bytes: 0
Promotion-ready bytes: 0
Verdict: oracle_sequence_dependency_reject
```

Conclusion: les 2 candidats sont exacts seulement parce que la sonde lit les
bytes precedents attendus. Dans le replay courant, les deux bytes precedents de
chaque candidat sont inconnus (`known_mask=0`, decoded `00`). Cette piste est
donc rejetee comme dependance oracle; la suite doit chercher un etat non-oracle
ou une regle capable de resoudre les prefixes de sequence.

La passe prefix-bootstrap cible alors les deux premiers bytes de chaque payload
mixed-value avec seulement des signaux non-oracle (`signal_*`, `prefix_*`,
sources externes, offset et dominant):

```text
output/tex_micro_mixed_value_payload_prefix_bootstrap/index.html
output/tex_micro_mixed_value_payload_prefix_bootstrap/rules.csv
output/tex_micro_mixed_value_payload_prefix_bootstrap/slots.csv
```

Etat courant:

```text
Prefix slots: 20
Feature sets: 7175
False-free byte rule sets: 342
Best false-free byte rule: dominant+signal_delta 4/0, unknown 16
Union candidate slots: 12
Union candidate rows: 8
Union conflict slots: 0
Sequence prerequisites covered: 4/4
Sequence candidates unlocked: 2/2
Promotion-ready bytes: 0
```

Conclusion: l'union des regles prefix non-oracle couvre les 4 bytes qui
bloquent les 2 candidats sequence, sans conflit entre predictions. C'est le
premier pont non-oracle vers la piste sequence; il faut maintenant revoir cette
union et la rejouer avec garde avant toute promotion.

Le replay prefix/sequence applique ensuite les 12 prefixes candidats, puis les
2 bytes sequence une fois leurs prerequis disponibles dans le replay simule:

```text
output/tex_micro_mixed_value_payload_prefix_sequence_replay/index.html
output/tex_micro_mixed_value_payload_prefix_sequence_replay/rows.csv
```

Etat courant:

```text
Prefix candidate bytes: 12
Prefix added bytes: 12
Prefix false bytes: 0
Sequence candidate bytes: 2
Sequence unlocked bytes: 2
Sequence added bytes: 2
Sequence false bytes: 0
Total added bytes: 14
Total false bytes: 0
Guarded replay bytes: 14
Promotion-ready bytes: 0
```

Conclusion: le pont prefix non-oracle debloque bien les 2 bytes sequence et
le replay simule ajoute 14 bytes sans faux. La prochaine etape est de
promouvoir ce replay garde dans la chaine de decodeur, ou de le transformer en
regles plus generales avant promotion.

Le replay garde est maintenant promu dans des buffers de fixtures regeneres:

```text
output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay/index.html
output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay/promotions.csv
```

Etat courant:

```text
Replay rows: 14
Promoted rows: 14
Mixed-value added bytes: 14
Mixed-value exact bytes: 14
Mixed-value false bytes: 0
Skipped known bytes: 0
Skipped rejected bytes: 0
Issue rows: 0
Total clean bytes: 9406
Remaining unresolved bytes: 8040
Full HD previews: 32
```

Conclusion: la promotion stricte ecrit les 12 prefixes et les 2 bytes sequence
dans les masques connus sans recouvrement ni faux positif. La prochaine etape
est de generaliser ces regles au-dela des lignes garde deja prouvees.

La generalisation post-promotion sonde ensuite les 22 slots high sequence avec
les nouveaux masques connus:

```text
output/tex_micro_mixed_value_payload_sequence_promoted_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_promoted_generalization/slots.csv
output/tex_micro_mixed_value_payload_sequence_promoted_generalization/rules.csv
```

Etat courant:

```text
Selected high slots: 22
Replayable unknown slots: 2
Target already known slots: 2
Blocked prerequisite slots: 18
Selected low feature sets: 1561
False-free feature sets: 0
Best feature set: pos16+dominant
Best correct/false: 1/1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: apres promotion, deux slots sequence supplementaires sont
replayables mais restent en conflit low (`6f` correct sur frontier 26,
`6e` faux contre `6d` sur frontier 50). Il faut maintenant splitter ce
contexte low ou debloquer plus de prefixes avant une autre promotion.

Le split low source-enriched teste ensuite les features sequence + source sur
les slots replayables:

```text
output/tex_micro_mixed_value_payload_sequence_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_low_split/rules.csv
output/tex_micro_mixed_value_payload_sequence_low_split/slots.csv
```

Etat courant:

```text
Features: 75
Feature sets: 2850
Replayable unknown slots: 2
False-free split sets: 409
Best false-free split: compressed_b-1
Best false-free split correct/unknown: 1/1
Best conflicted correct/false: 1/1
Promotion-candidate bytes: 1
Issue rows: 0
```

Le replay promu ecrit ce candidat unique:

```text
output/tex_micro_mixed_value_payload_sequence_low_split_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_low_split_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_low_split_promoted_replay/promotions.csv
```

Etat courant:

```text
Split candidate rows: 1
Promoted rows: 1
Low-split added bytes: 1
Low-split exact bytes: 1
Low-split false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9407
Remaining unresolved bytes: 8039
Full HD previews: 32
```

Conclusion: le byte `6f` de `dinodead.pcx` frontier 26 offset absolu 412 est
maintenant promu via `compressed_b-1=b6`. La prochaine etape est d'elargir les
prefixes connus pour debloquer les 18 slots sequence encore bloques.

L'expansion de prerequis sequence sonde ensuite les bytes inconnus qui bloquent
ces slots, en repartant du replay promu low-split:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion/slots.csv
```

Etat courant:

```text
Selected high slots: 22
Blocked sequence slots: 18
Prerequisite slots: 30
Unknown prerequisite slots: 26
Features: 84
Feature sets: 3570
False-free rule sets: 511
Best feature set: prev2
Best correct/unknown: 10/16
Union candidate slots: 10
Union conflict slots: 0
Unlocked sequence slots: 7
Promotion-candidate bytes: 10
Promotion-ready bytes: 0
Issue rows: 0
```

Le replay promu applique ces candidats de prerequis gardes:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/promotions.csv
```

Etat courant:

```text
Candidate rows: 10
Promoted rows: 10
Prerequisite added/exact bytes: 10/10
Prerequisite false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9417
Remaining unresolved bytes: 8029
Full HD previews: 32
```

Conclusion: 10 bytes de prerequis `6f` dans `dinodead.pcx` frontier 26 sont
maintenant promus sans conflit ni faux positif. Ils debloquent 7 slots sequence;
la prochaine etape est de reevaluer la generalisation sequence sur ce replay
enrichi.

Le split low post-prerequis reprend alors le replay enrichi:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/slots.csv
```

Etat courant:

```text
Features: 75
Feature sets: 2850
Replayable unknown slots: 4
Target known slots: 7
Blocked prerequisite slots: 11
False-free split sets: 120
Best false-free split: best_b-1+compressed_d1
Best false-free split correct/unknown: 2/2
Best conflicted correct/false: 2/1
Promotion-candidate bytes: 2
Issue rows: 0
```

Le replay promu ecrit ces 2 candidats supplementaires:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/promotions.csv
```

Etat courant:

```text
Split candidate rows: 2
Promoted rows: 2
Low-split added bytes: 2
Low-split exact bytes: 2
Low-split false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9419
Remaining unresolved bytes: 8027
Full HD previews: 32
```

Conclusion: les bytes `6e` de `dinodead.pcx` frontier 26 offsets absolus 99 et
417 sont maintenant promus via `best_b-1+compressed_d1=00|+j`. La prochaine
etape est de reevaluer la sequence avec ces deux valeurs connues.

La generalisation residuelle apres ce split low mesure ensuite le nouvel etat:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization/slots.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization/rules.csv
```

Etat courant:

```text
Selected high slots: 22
Replayable unknown slots: 2
Target already known slots: 9
Blocked prerequisite slots: 11
Selected low feature sets: 1561
False-free feature sets: 0
Best feature set: control
Best correct/false/unknown: 0/1/1
Promotion-ready bytes: 0
Issue rows: 0
```

Le split low residuel elargit alors la recherche a 3 features:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3/slots.csv
```

Etat courant:

```text
Features: 75
Feature sets: 70375
Replayable unknown slots: 2
Target known slots: 9
Blocked prerequisite slots: 11
False-free split sets: 0
Promotion-candidate bytes: 0
Issue rows: 0
```

L'expansion residuelle de prerequis pousse aussi les combinaisons a 3 features:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3/slots.csv
```

Etat courant:

```text
Selected high slots: 22
Blocked sequence slots: 11
Prerequisite slots: 20
Unknown prerequisite slots: 16
Features: 84
Feature sets: 98854
False-free rule sets: 0
Union candidate slots: 0
Union conflict slots: 0
Unlocked sequence slots: 0
Promotion-candidate bytes: 0
Issue rows: 0
```

Conclusion: les deux slots replayables restants sont des `6d` sur
`dinodead.pcx` frontier 26 offset absolu 443 et frontier 50 offset absolu 218.
Les splits low jusqu'a 3 features et les prerequis jusqu'a 3 features ne
donnent plus de candidat false-free. La prochaine piste doit ajouter une
nouvelle famille de features de prerequis/sequence au lieu de recombiner les
features actuelles.

L'expansion corpus de prerequis remplace alors l'apprentissage limite aux
prerequis par les 567 entrees byte-level mixed-value, toujours en
leave-one-row-out:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/slots.csv
```

Etat courant:

```text
Training entries: 567
Unknown prerequisite slots: 16
Features: 84
Feature sets: 98854
False-free rule sets: 737
Best correct/unknown: 2/14
Union candidate slots: 8
Union conflict slots: 0
Unlocked sequence slots: 5
Promotion-candidate bytes: 8
Issue rows: 0
```

Le replay promu applique ces 8 prerequis corpus:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/promotions.csv
```

Etat courant:

```text
Candidate rows: 8
Promoted rows: 8
Prerequisite added/exact bytes: 8/8
Prerequisite false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9427
Remaining unresolved bytes: 8019
Full HD previews: 32
```

Conclusion: l'apprentissage corpus debloque 5 slots sequence sans conflit et
porte le replay propre a 9427 bytes. La prochaine etape est de reevaluer la
sequence sur ce replay corpus enrichi.

Le split low corpus reprend ce replay enrichi avec des combinaisons jusqu'a
3 features:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/slots.csv
```

Etat courant:

```text
Features: 75
Feature sets: 70375
Replayable unknown slots: 7
Target known slots: 9
Blocked prerequisite slots: 6
False-free split sets: 10333
Best false-free split: best_d0+compressed_d1
Best false-free split correct/unknown: 3/4
Best conflicted correct/false: 3/1
Promotion-candidate bytes: 3
Issue rows: 0
```

Le replay promu applique ces 3 candidats low-split:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/promotions.csv
```

Etat courant:

```text
Split candidate rows: 3
Promoted rows: 3
Low-split added bytes: 3
Low-split exact bytes: 3
Low-split false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9430
Remaining unresolved bytes: 8016
Full HD previews: 32
```

Conclusion: le split low corpus promeut 3 bytes supplementaires sans faux
positif. La prochaine etape est de reevaluer la sequence apres cette promotion
corpus low-split.

Le second split low corpus reprend le replay a 9430 bytes propres:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/slots.csv
```

Etat courant:

```text
Features: 75
Feature sets: 70375
Replayable unknown slots: 4
Target known slots: 12
Blocked prerequisite slots: 6
False-free split sets: 20
Best false-free split: best_d2+compressed_h0
Best false-free split correct/unknown: 1/3
Promotion-candidate bytes: 1
Issue rows: 0
```

Le replay promu ecrit ce candidat unique:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/fixtures.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/promotions.csv
```

Etat courant:

```text
Split candidate rows: 1
Promoted rows: 1
Low-split added bytes: 1
Low-split exact bytes: 1
Low-split false bytes: 0
Skipped known/rejected bytes: 0/0
Issue rows: 0
Total clean bytes: 9431
Remaining unresolved bytes: 8015
Full HD previews: 32
```

Conclusion: le second split low corpus ajoute un byte propre de plus. La
prochaine etape est de reevaluer la sequence sur le replay a 9431 bytes propres.

La passe adjacent-known exploite ensuite uniquement les bytes non nuls deja
connus juste avant ou juste apres un prerequis encore inconnu:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known/slots.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known/rules.csv
```

Etat courant:

```text
Unknown prerequisite slots: 8
Adjacent candidate slots: 2
Adjacent false/conflict slots: 0/0
Unlocked sequence slots: 2
Promotion-candidate bytes: 2
Issue rows: 0
```

Le replay promu applique ces deux premiers prerequis, puis deux autres passes
propagent les runs adjacents nouvellement connus:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/index.html
```

Etat courant cumule:

```text
First adjacent-known promoted rows: 2/2
Second adjacent-known promoted rows: 1/1
Third adjacent-known promoted rows: 1/1
Adjacent-known added/exact bytes: 4/4
Adjacent-known false bytes: 0
Issue rows: 0
Total clean bytes: 9435
Remaining unresolved bytes: 8011
Full HD previews: 32
```

Conclusion: la propagation adjacent-known ajoute 4 prerequis propres dans les
runs de `dinodead.pcx` frontier 80 et debloque 4 slots sequence au total. La
prochaine etape est de reevaluer la sequence sur le replay a 9435 bytes propres.

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
