# Mise au point du projet

Date: 2026-06-20

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

Audit runtime:

```sh
python3 tools/lolg_runtime_fullhd_audit.py
```

Validation actuelle:

```text
Full HD audit: pass
Gates: 252/252
Full HD PNGs: 177463
Dashboard cards: 6
Dashboard links: 809
Runtime audit: gap
Runtime components: 8
Runtime ready components: 1
Runtime info components: 2
Runtime gaps: 2
```

## Ce qui est stable

- `RUN_HD.sh` est le lanceur HD principal.
- `RUN_HD_PCX_FULLHD.sh` est le lanceur runtime PCX Full HD non destructif:
  il regenere `output/fullhd_pcx_runtime_launch/` avec les MIX du pack
  `mod_mix_pcx_fullhd/` et laisse les MIX actifs inchanges.
- Les reglages de qualite du jeu sont reappliques au lancement.
- Les images fixes PCX sont exportees et verifiees en 1920x1080.
- Un pack MIX PCX 1920x1080 experimental existe pour les 37 PCX de
  `GLOBAL.MIX`/`LOCAL.MIX`; il n'est pas installe dans les MIX actifs.
- Un staging de smoke test non destructif peut etre regenere dans
  `output/fullhd_pcx_runtime_smoke/`.
- Le smoke DOSBox offscreen du staging PCX Full HD tient jusqu'au timeout de
  45s avec stage/ISO/VESA/swap confirmes, lectures tracees des deux MIX Full
  HD, lecture de l'entree PCX cible `LOCAL:0fe8e7df`, et frame SDL 640x480 non
  vide capturee apres sa lecture complete (`after_pcx_frame_temporal_proof=1`);
  une variante sentinelle isolee prouve que cette payload PCX affecte le
  framebuffer capture (`sentinel_proof=pass`).
- Les VQA ont un vrai rendu frame par frame exporte en Full HD.
- La faisabilite runtime VQA est auditee separement: elle confirme les 1955
  entrees et 171167 frames Full HD exportees. La readiness repack confirme
  aussi 1955/1955 entrees mappees et 66/66 archives en roundtrip exact.
  Un premier writer WVQA Full HD produit maintenant un batch principal de 1568
  payloads de remplacement et deux batches incrementaux `--missing-only` de 3
  puis 6 payloads; le rapport writer principal valide 73647/73647 frames
  1920x1080 au redecode, et le dernier batch incremental valide 546/546 frames
  supplementaires. Un seed
  writer d'archives ajoute 8 payloads cibles, valide 1675/1675 frames, et la
  racine runtime atteint 1614/1955 payloads; le builder ecrit maintenant 66/66
  MIX runtime partiels dans `mod_mix_vqa_fullhd/`; 341 payloads restent
  manquants, et 51 remplacements de `L20_BBI.MIX` sont differes pour rester sous
  la limite body 32 bits du format MIX.
  La primitive LCW literal a maintenant 11 roundtrips sans echec et isole 374
  entrees natives exact-block comme cibles de fixture.
  Le writer de fixture WVQA native assemble un payload `FORM/WVQA` CBFZ/VPTZ
  LCW literal et valide 20/20 frames au redecode.
- La readiness de capture runtime `.tex` est auditee separement: Xvfb et Wine
  sont detectes. L'essai Xvfb/Wine standard atteint le bootstrap (`MMX`), puis
  sort en `exited_1` sur le rendu D3D/pixel-format; une variante
  `renderer=no3d` reste vivante jusqu'au timeout controle. Les entrees reelles
  `real_upload_capture`, `real_surface` et `real_provenance` manquent encore.
  Les traces `winedbg` standard et `no3d` confirment que les 7 breakpoints
  payload-offset sont acceptes, mais qu'aucun n'est touche en 90s sans pilotage
  de gameplay ni hook natif.
- Les assets CDCACHE ont un pack HD verifie, avec 3104 assets references.
- L'inventaire Full HD contient 177463 PNGs verifies en 1920x1080, sans issue.
- L'audit runtime separe les exports valides des assets effectivement charges
  par le jeu.
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
.tex augmented unresolved unique PCX references: 49
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
output/vqa_runtime_feasibility/index.html
output/vqa_runtime_feasibility/summary.csv
output/vqa_runtime_feasibility/requirements.csv
output/vqa_runtime_repack_readiness/index.html
output/vqa_runtime_repack_readiness/summary.csv
output/vqa_runtime_repack_readiness/requirements.csv
output/vqa_runtime_repack_readiness/archives.csv
output/vqa_runtime_repack_readiness/entries.csv
output/vqa_runtime_pack_build/index.html
output/vqa_runtime_pack_build/summary.csv
output/vqa_runtime_pack_build/requirements.csv
output/vqa_runtime_pack_build/archives.csv
output/vqa_runtime_pack_build/entries.csv
output/vqa_lcw_literal_probe/index.html
output/vqa_lcw_literal_probe/summary.csv
output/vqa_lcw_literal_probe/requirements.csv
output/vqa_lcw_literal_probe/candidates.csv
output/vqa_native_exact_fixture_writer/index.html
output/vqa_native_exact_fixture_writer/summary.csv
output/vqa_native_exact_fixture_writer/requirements.csv
output/vqa_native_exact_fixture_writer/frames.csv
output/vqa_fullhd_replacement_writer/index.html
output/vqa_fullhd_replacement_writer/summary.csv
output/vqa_fullhd_replacement_writer/requirements.csv
output/vqa_fullhd_replacement_writer/frames.csv
```

Etat runtime VQA: `gap`. Le rapport de faisabilite liste 9 requirements: les
requirements `wvqa_encoder`, `mix_repack_roundtrip`, `lcw_literal_encoder`,
`wvqa_native_fixture_writer` et `palette_codebook_pointer_encoder` passent
(`mapped_entries=1955/1955`, `roundtrip_archives=66/66`,
`roundtrip_cases=11`, `roundtrip_failures=0`, `matched_frames=20/20`,
`fullhd_writer_validated_frames=73647/73647`, `exact_block_ratio=0.917133`),
tandis que 4 restent ouverts:
`mix_repack`, `lcw_format80_encoder`, `audio_handling` et
`cbp_update_encoder`. Le build de pack VQA reste `gap` avec
`replacement_entries=1614/1955`, `applied_replacements=1563/1955`,
`deferred_replacements=51`, `missing_replacements=341` et
`output_archives=66/66`.

## Textures .tex

Le vrai decodeur `.tex` est le chantier actif. L'etat actuel est proprement
instrumente: les rapports isolent les gaps, les frontieres, les runs, les
tokens, les controles et les cas non resolus. Les promotions automatiques sont
conservatrices: quand une hypothese ne produit pas une regle robuste, elle reste
en revue.

Readiness runtime reelle:

```text
output/tex_runtime_real_capture_readiness/index.html
output/tex_runtime_real_capture_readiness/summary.csv
output/tex_runtime_real_capture_readiness/requirements.csv
output/tex_runtime_real_capture_readiness/run_xvfb_capture_session.sh
output/tex_runtime_real_capture_attempt/index.html
output/tex_runtime_real_capture_attempt/summary.csv
output/tex_runtime_real_capture_attempt/targets.csv
output/tex_runtime_real_capture_attempt_no3d/index.html
output/tex_runtime_real_capture_attempt_no3d/summary.csv
output/lolg95_winedbg_payload_trace_attempt/index.html
output/lolg95_winedbg_payload_trace_attempt/summary.csv
output/lolg95_winedbg_payload_trace_attempt/trace.tsv
output/lolg95_winedbg_payload_trace_attempt/raw.log
output/lolg95_winedbg_payload_trace_attempt_no3d/index.html
output/lolg95_winedbg_payload_trace_attempt_no3d/summary.csv
output/lolg95_winedbg_payload_trace_attempt_no3d/trace.tsv
output/lolg95_winedbg_payload_trace_attempt_no3d/raw.log
```

Etat actuel: `gap`. Xvfb et Wine sont disponibles, mais la preflight reste
`missing_real_provenance`; les trois entrees attendues sont encore absentes:
`real_upload_capture`, `real_surface` et `real_provenance`. L'essai Xvfb/Wine
standard consigne `session_status=exited_1` et `timed_out=0`: LOLG95 atteint le
bootstrap MMX, puis echoue sur le rendu D3D/pixel-format et le changement de
mode display. La variante `renderer=no3d` consigne
`session_status=started_timeout` et `timed_out=1`, avec le prefixe Wine isole
`output/tex_runtime_real_capture_attempt_no3d/wineprefix`; elle evite la sortie
rapide, mais ne cree toujours aucun artefact dans `captures/`. Le prochain
verrou est donc le hook/logger TE qui doit ecrire ces fichiers pendant la
session Wine. Les essais `winedbg` standard et `no3d` consignent
`contract_breakpoints=7`, `breakpoint_hits=0` et `extracted_rows=0`; les
breakpoints sont poses, mais le flux actuel n'atteint pas les probes
payload-offset.

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

La chaine seed rejoue ensuite les gradients repetes exacts a distance 320,
teste leurs shifts, deltas, phases et tokens opcode/payload:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_payload_opcode_probe/index.html
```

Etat courant:

```text
Repeated gradient payload bytes: 244
Copy-distance-320 bytes: 244
Seed candidate bytes: 122
Copy-unlock bytes: 122
Total seed + unlock potential: 244
Shift family repeated bytes: 122
Repeated exact shift-set bytes: 0
Delta selector repeated deterministic bytes: 0
Delta phase/state repeated deterministic bytes: 0 / 0
Opcode sequence repeated bytes: 0
Semantic opcode repeated bytes: 0
Payload opcode repeated bytes: 46
Best payload opcode token: palette_index = 36 repeated / 122 conflicted
Promotion-ready bytes: 0
```

Conclusion: les deux seeds exacts sont reels, mais les deltas restent soit
oracle-only, soit singletons, soit conflictuels. Meme le payload opcode ne
stabilise que 46 octets repetes avec 122 octets conflictuels; cette piste doit
donc rester un indice de structure, pas une promotion.

La passe spatial connu nonlocal durcit ensuite la recherche: elle ne copie que
depuis les bytes deja marques connus dans le replay palette/formule, puis teste
les distances spatiales larges et transforms simples:

```text
output/tex_gradient_nonlocal_known_spatial/index.html
output/tex_gradient_nonlocal_known_spatial/rules.csv
output/tex_gradient_nonlocal_known_spatial/slots.csv
```

Etat courant:

```text
Unknown gradient slots: 1564
Known spatial source samples: 8047
Candidate predictions: 56329
Distance/transform rules: 224
False-free rules: 0
Best known-spatial rule: +128 / sub1 = 25 exact / 634 false
Identity -320: 2 exact / 110 false
Identity +320: 3 exact / 104 false
Slots with any exact candidate: 326
Promotion candidate bytes: 0
```

Conclusion: meme avec des sources non-oracle deja connues, les copies
spatiales non locales sont massivement fausses. La suite doit chercher un etat
de sequence plus large, pas une distance/transform spatiale locale ou
semi-locale.

La passe etat sequence connue utilise ensuite uniquement les bytes deja connus
autour de chaque slot gradient: voisins immediats, dernier/prochain byte connu,
phase dans la ligne, compteurs prefix et position:

```text
output/tex_gradient_sequence_known_state/index.html
output/tex_gradient_sequence_known_state/rules.csv
output/tex_gradient_sequence_known_state/slots.csv
```

Etat courant:

```text
Sequence slots: 1564
Feature sets: 2047
Full false-free feature sets: 0
Best full rule: top_nibble + rel_mod16 + prev_gap_bucket = 34 exact / 42 false
High false-free feature sets: 106
Best high false-free slots: 320
Best high false-free rule: gradient_class + top_nibble + prev_known_byte
Best high broad rule: top_nibble + prev_gap_bucket + next_gap_bucket = 491 exact / 24 false
Best high low-false rule: top_nibble + prev_known_byte + next_known_byte = 351 exact / 3 false
Low false-free feature sets: 0
Best low rule: top_nibble + rel_mod16 + prev_gap_bucket = 36 exact / 40 false
Promotion candidate bytes: 0
```

Conclusion: l'etat de sequence connu donne un signal high-nibble net et plus
large que les copies spatiales, mais il ne resout ni le byte complet ni le
low-nibble. Il faut garder ce high comme indice de phase et chercher un
resolveur low/full distinct.

La passe high-safe low de sequence applique ensuite la meilleure regle
high-nibble false-free (`gradient_class + top_nibble + prev_known_byte`) puis
cherche le low/full uniquement dans les slots high-safe:

```text
output/tex_gradient_sequence_high_safe_low/index.html
output/tex_gradient_sequence_high_safe_low/rules.csv
output/tex_gradient_sequence_high_safe_low/slots.csv
```

Etat courant:

```text
High-safe slots: 320
High-safe rows: 10
Low feature sets: 2601
Full false-free sets: 18
Best full false-free slots: 5
Best full rule: x_mod8 + prev_gap_bucket + unknown_before_mod16 = 50 exact / 102 false
Target-low false-free sets: 18
Best target-low false-free slots: 5
Best target-low rule: x_mod8 + prev_gap_bucket + unknown_before_mod16 = 50 exact / 102 false
Promotion candidate bytes: 0
```

Conclusion: le high-safe de sequence ne suffit pas; les false-free low/full ne
couvrent que 5 slots et les meilleurs contextes reutilisables restent faux. La
suite doit enrichir l'etat low, pas promouvoir cette sous-piste.

La passe sequence high-safe + source-profile joint ensuite ces 320 slots avec
les fenetres source-profile deja calculees:

```text
output/tex_gradient_sequence_high_safe_source_profile_low/index.html
output/tex_gradient_sequence_high_safe_source_profile_low/rules.csv
output/tex_gradient_sequence_high_safe_source_profile_low/slots.csv
```

Etat courant:

```text
Joined high-safe slots: 320
High-safe rows: 10
Feature sets: 26938 focused
Full false-free sets: 271
Best full false-free slots: 6
Best full rule: x_mod8 + prev_gap_bucket + unknown_before_mod16 = 50 exact / 102 false
Best near-full rule: rel_mod8 + prev4 + source_low = 10 exact / 4 false
Target-low false-free sets: 271
Best target-low false-free slots: 6
Best target-low rule: x_mod8 + prev_gap_bucket + unknown_before_mod16 = 50 exact / 102 false
Best near-low rule: rel_mod8 + prev4 + source_low = 10 exact / 4 false
Promotion candidate bytes: 0
```

Conclusion: l'ajout source-profile ne transforme pas le high-safe de sequence
en resolveur low/full. La couverture false-free gagne seulement un slot (6 au
lieu de 5) et les meilleurs contextes reutilisables restent bruites.

La passe row/corpus ajoute ensuite les positions absolues/modulo, la position
dans la plage, la forme de ligne et les cles archive/fichier aux 320 slots
sequence high-safe + source-profile:

```text
output/tex_gradient_sequence_high_safe_row_corpus_low/index.html
output/tex_gradient_sequence_high_safe_row_corpus_low/rules.csv
output/tex_gradient_sequence_high_safe_row_corpus_low/slots.csv
```

Etat courant:

```text
Row/corpus slots: 320
High-safe rows: 10
Feature sets: 59737 row_corpus_focused
Full false-free sets: 656
Best full false-free slots: 10
Best full rule: end_mod16 + source_target_delta_mod32 = 56 exact / 136 false
Best near-full rule: x_mod8 + src_rel_mod8 + offset_delta_bucket + row_third = 17 exact / 5 false
Target-low false-free sets: 656
Best target-low false-free slots: 10
Best target-low rule: end_mod16 + source_target_delta_mod32 = 56 exact / 136 false
Best near-low rule: x_mod8 + src_rel_mod8 + offset_delta_bucket + row_third = 17 exact / 5 false
Promotion candidate bytes: 0
```

Conclusion: row/corpus donne une petite borne false-free supplementaire (10
slots) mais reste trop sparse, et le meilleur contexte large est encore plus
bruite que le source-profile seul. La suite doit chercher un transform/low-split
gradient plutot qu'une cle positionnelle directe.

La passe transform-low teste ensuite le low direct, les deltas, signed-deltas et
xor du low contre la source, les voisins connus et les bases positionnelles des
slots row/corpus:

```text
output/tex_gradient_sequence_high_safe_transform_low/index.html
output/tex_gradient_sequence_high_safe_transform_low/rules.csv
output/tex_gradient_sequence_high_safe_transform_low/slots.csv
```

Etat courant:

```text
Row/corpus slots: 320
Feature sets: 4101 focused
Transform targets: 40
Candidate rules: 164040
Predicted rules: 75443
False-free transform sets: 5962
Best false-free slots: 10
Best false-free rule: xor:x + x_mod8 + src_rel_mod4 + row_quarter
Best broad rule: xor:source_delta + end_mod16 + source_target_delta_mod32 = 56 exact / 136 false
Best low-false rule: xor:x + x_mod8 + src_rel_mod8 + offset_delta_bucket + row_third = 17 exact / 5 false
Promotion candidate bytes: 0
```

Conclusion: les transforms low ne generalisent pas mieux que le direct
row/corpus. Le meilleur cas false-free reste limite a 10 slots et le meilleur
cas large conserve 136 faux; la piste suivante doit viser une grammaire
residuelle source-window/controle plutot qu'un low-split simple.

La passe source-window scanne ensuite les offsets voisins autour du
`source_profile_offset` puis teste un gating hors-ligne des meilleurs candidats:

```text
output/tex_gradient_sequence_high_safe_source_window/index.html
output/tex_gradient_sequence_high_safe_source_window/fixed_candidates.csv
output/tex_gradient_sequence_high_safe_source_window/gated_rules.csv
output/tex_gradient_sequence_high_safe_source_window/slots.csv
```

Etat courant:

```text
Slots: 320
Scan radius: 64
Best fixed low: +21:lowsigned-7 = 119 exact / 201 false
Best fixed full identity: +0:identity = 23 exact / 297 false
Gate candidates: 15
Gate feature sets: 5491
Best gated rule: +20:lowxor9 + unknown_before_mod16 + target_x_mod32 = 30 exact / 30 false
Best gated false-free: +21:lowsigned-7 + x_mod8 + row_quarter + row_third = 5 slots
Promotion candidate bytes: 0
```

Conclusion: la fenetre source contient un signal low reel mais trop diffus:
le meilleur offset fixe touche 119 slots tout en produisant 201 faux, et le
meilleur gating hors-ligne reste equilibre a 30/30. La suite doit revenir a un
etat residuel controle/opcode gradient plutot qu'a une copie de fenetre source.

La passe controle/opcode high-safe projette alors les 320 slots residuels sur
les ancres `control_ref_offset`, l'ancre de depart reconstruite, les bytes
`control_prefix`/`fragment`, les signatures de fenetre et les bins
`span_index`/`op_index`:

```text
output/tex_gradient_sequence_high_safe_control_opcode/index.html
output/tex_gradient_sequence_high_safe_control_opcode/summary.csv
output/tex_gradient_sequence_high_safe_control_opcode/candidates.csv
output/tex_gradient_sequence_high_safe_control_opcode/contexts.csv
output/tex_gradient_sequence_high_safe_control_opcode/slots.csv
```

Etat courant:

```text
Slots: 320
Slot rows: 10
Control/start low exact: 22 / 20
Prefix/fragment low exact: 9 / 30
Best low opcode context: state_source_mix = 30 correct / 34 false
Best byte opcode context: state_source_mix = 30 correct / 34 false
Best high context: control_delta_pos16 = 297 correct / 0 false
Best low false-free slots: 0
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les contextes controle/opcode gardent surtout le signal high deja
borne par le high-safe; le low reste bruite et aucun contexte low false-free
n'apparait. La prochaine piste doit viser une grammaire de transition low
cross-row plutot qu'une ancre controle/opcode directe.

La passe de transition low cross-row compare ensuite les sequences de 32 lows
entre rows (`prev_file`, `next_file`, `dist+320`, `dist-320` et variantes meme
frontier), avec offsets relatifs voisins et transforms `id`, `+n`, `xor n`:

```text
output/tex_gradient_sequence_high_safe_row_transition/index.html
output/tex_gradient_sequence_high_safe_row_transition/summary.csv
output/tex_gradient_sequence_high_safe_row_transition/fixed_candidates.csv
output/tex_gradient_sequence_high_safe_row_transition/gated_rules.csv
output/tex_gradient_sequence_high_safe_row_transition/slots.csv
```

Etat courant:

```text
Slots: 320
Slot rows: 10
Relations: 6
Fixed candidates: 990
Best fixed transition: prev_file:+1:xor0 = 75 exact / 204 false
Gate candidates: 14
Gate feature sets: 379
Best gated transition: same_frontier-320:-2:xor1 + target_x_mod32 + gradient_class = 18 exact / 20 false
Best gated false-free: same_frontier-320:-2:xor1 + rel_mod16 + row_quarter + source_low = 8 slots
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: la transition cross-row apporte plus de signal brut que les ancres
controle/opcode, mais reste trop fausse en contexte large et trop faible en
false-free. La suite doit chercher une grammaire low locale/Markov propre aux
rows plutot qu'une propagation directe depuis une autre row.

La passe Markov low row-local teste ensuite les transitions internes d'une row:
`prev_low`, paire precedente, delta precedent, position de sequence, bins
`target_x`/quart/tiers et etat opcode, toujours en leave-one-row-out:

```text
output/tex_gradient_sequence_high_safe_row_markov/index.html
output/tex_gradient_sequence_high_safe_row_markov/summary.csv
output/tex_gradient_sequence_high_safe_row_markov/candidates.csv
output/tex_gradient_sequence_high_safe_row_markov/contexts.csv
output/tex_gradient_sequence_high_safe_row_markov/slots.csv
```

Etat courant:

```text
Slots: 320
Slot rows: 10
Context families: 23
Best low Markov: prev_delta_seq_gradient = 49 correct / 92 false
Best delta Markov: prev_pair_seq = 50 correct / 60 false
Best step Markov: prev_pair_seq = 54 correct / 57 false
Best delta false-free: prev_low_quarter_third_offset = 9 slots
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: le Markov local capte quelques transitions recurrentes, mais le
meilleur contexte large reste plus faux que correct et le false-free est trop
faible. La suite doit viser un modele low par templates de row ou une grammaire
de forme plus globale, pas seulement un etat Markov court.

La passe template low row teste ensuite des contextes de position/forme sans
dependre de lows precedents: position de sequence, `target_x`, tiers/quart de
row, frontier/opcode, source profile et formes de row:

```text
output/tex_gradient_sequence_high_safe_row_template/index.html
output/tex_gradient_sequence_high_safe_row_template/summary.csv
output/tex_gradient_sequence_high_safe_row_template/candidates.csv
output/tex_gradient_sequence_high_safe_row_template/contexts.csv
output/tex_gradient_sequence_high_safe_row_template/slots.csv
```

Etat courant:

```text
Slots: 320
Slot rows: 10
Context families: 25
Best row-template low: rel4_target_x_third_start_band = 55 correct / 94 false
Best row-template bucket: target_x_quarter_edge_start_band = 90 correct / 103 false
Best false-free low: rel8_quarter_frontier_source_low = 9 slots
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: le template exact reste bloque, mais le bucket low grossier donne
un signal superieur au low exact. La piste suivante doit scinder le probleme en
bucket low puis resolver intra-bucket, au lieu de chercher directement le low
exact.

La passe split bucket low teste donc le meilleur cas apres split grossier:
bucket reel connu (`lo=6/7/8`, `mid=9/a`, `hi=b/c`), puis resolution du low
exact avec les memes contextes leave-one-row-out et quelques contextes
sequence/source dedies:

```text
output/tex_gradient_sequence_high_safe_low_bucket_split/index.html
output/tex_gradient_sequence_high_safe_low_bucket_split/summary.csv
output/tex_gradient_sequence_high_safe_low_bucket_split/buckets.csv
output/tex_gradient_sequence_high_safe_low_bucket_split/candidates.csv
output/tex_gradient_sequence_high_safe_low_bucket_split/slots.csv
```

Etat courant:

```text
Slots: 320
Buckets: lo|mid|hi
Context families: 36
Combined best split: 150 correct / 60 false / 110 unknown
Combined baseline inside buckets: 234 correct / 320 slots
Best bucket resolver: mid / bucket_prev_low_seq = 69 correct / 41 false
Combined false-free slots: 30
Promotion candidate bytes: 30
Promotion-ready bytes: 0
```

Conclusion: le split par bucket confirme que le bucket grossier porte du
signal, mais le resolver exact local ne bat pas la baseline majoritaire par
bucket. La suite doit modeliser les exceptions minoritaires (`7/6`, `a`, `c`)
plutot qu'un resolver exact general par bucket.

La passe exceptions low isole ensuite uniquement les valeurs minoritaires de
chaque bucket (`lo:7`, `lo:6`, `mid:a`, `hi:c`) et teste des selecteurs locaux
qui ne predisent une exception que si le contexte d'entrainement est strictement
cette exception:

```text
output/tex_gradient_sequence_high_safe_low_exception/index.html
output/tex_gradient_sequence_high_safe_low_exception/summary.csv
output/tex_gradient_sequence_high_safe_low_exception/targets.csv
output/tex_gradient_sequence_high_safe_low_exception/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception/slots.csv
```

Etat courant:

```text
Slots: 320
Majority slots: 234
Exception slots: 86
Exception targets: lo:7|lo:6|mid:a|hi:c
Best exception target: mid:a / bucket_frontier_source = 15 correct / 14 false
Combined exception best: 16 correct / 17 false / 287 unknown
Combined false-free slots: 0
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les selecteurs locaux d'exceptions sont trop bruites et ne
produisent aucun slot false-free. La suite doit chercher un alignement
cross-row/corpus des exceptions, pas une selection locale par position/source.

La passe alignement exceptions low teste ensuite les masques d'exceptions entre
rows: chaque row source peut predire ses exceptions vers une row cible avec un
shift de sequence `-12..12`, en mode exact ou en mode contraint `same_bucket`.

```text
output/tex_gradient_sequence_high_safe_low_exception_alignment/index.html
output/tex_gradient_sequence_high_safe_low_exception_alignment/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_alignment/alignments.csv
output/tex_gradient_sequence_high_safe_low_exception_alignment/slots.csv
```

Etat courant:

```text
Slots: 320
Exception slots: 86
Alignments: 4391
Best alignment: same_bucket shift 8 = 6 correct / 0 false
Best false-free alignment: same_bucket shift 8 = 6 slots
Same-bucket false-free alignments: 165
Promotion candidate bytes: 6
Promotion-ready bytes: 0
```

Conclusion: il existe un petit signal pair-row propre, mais il est lie a une
row source/cible specifique et ne suffit pas pour promouvoir. La suite doit
revoir ces alignements false-free et chercher une regle de famille de rows avant
toute injection.

La passe revue alignement exceptions low regroupe ensuite les 165 alignements
`same_bucket` false-free et rejoue leurs familles de selecteurs contre tous les
alignements `same_bucket`: shift, frontiers, deltas de start, mods de start,
low predit, ainsi que les cles row-keyed exactes.

```text
output/tex_gradient_sequence_high_safe_low_exception_alignment_review/index.html
output/tex_gradient_sequence_high_safe_low_exception_alignment_review/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_alignment_review/selectors.csv
output/tex_gradient_sequence_high_safe_low_exception_alignment_review/false_free_selectors.csv
```

Etat courant:

```text
Same-bucket alignments: 2141
False-free alignments: 165
False-free alignment slots: 269
Selector families: 17
Selector rows: 1783
Best non-row false-free selector: start_delta_shift / 811|sh=8 = 6 slots
Best non-row selector alignments: 1
Broad false-free selectors: 0
Promotion candidate bytes: 6
Promotion-ready bytes: 0
```

Conclusion: les alignements false-free sont reels mais restent etroits. Aucun
selecteur large non-row ne survit au replay global; la suite doit chercher un
support de famille de rows/corpus avant de convertir ces 6 bytes en candidats.

La passe familles row exceptions low teste ensuite ce support explicitement en
regroupant les alignements `same_bucket` par signatures de row: frontier,
`start_mod320`, bandes de start, paires cible/source et shift.

```text
output/tex_gradient_sequence_high_safe_low_exception_row_family/index.html
output/tex_gradient_sequence_high_safe_low_exception_row_family/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_row_family/families.csv
output/tex_gradient_sequence_high_safe_low_exception_row_family/false_free_families.csv
```

Etat courant:

```text
Same-bucket alignments: 2141
False-free alignments: 165
Family kinds: 10
Family rows: 1217
Best row-family false-free: frontier_band_pair_shift / 18|640-959->28|0-319|sh=8 = 6 slots
Best row-family alignments: 1
Robust row families: 0
Narrow row families: 277
Promotion candidate bytes: 6
Promotion-ready bytes: 0
```

Conclusion: les familles de rows confirment que le signal reste trop etroit:
aucune famille robuste multi-row ne couvre les exceptions sans faux. La suite
doit chercher un etat externe corpus/source plutot que prolonger les selecteurs
pair-row.

La passe etat externe exceptions low teste alors les champs corpus/source deja
extraits autour des memes 86 exceptions minoritaires: offset/source/control,
prefix/fragment, fenetre head/tail, transition reconstruite, couples
source/control et position corpus. Chaque contexte est rejoue en
leave-one-row-out.

```text
output/tex_gradient_sequence_high_safe_low_exception_external_state/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_state/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_state/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_state/candidates.csv
```

Etat courant:

```text
Context families: 27
Best external target: mid:a / prefix_low_seq = 18 correct / 21 false
Combined external-state best: 20 correct / 24 false
Combined false-free slots: 0
Promotion candidate bytes: 0
Promotion-ready bytes: 0
```

Conclusion: les champs externes disponibles ne separant pas les lows
minoritaires sans faux, ils bornent plutot un manque de pre-requis. La suite
doit chercher un resolveur payload/corpus plus amont avant de relancer les
exceptions low.

La passe etat prerequis exceptions low joint ensuite ces memes slots aux
fixtures du replay `sequence_low_copy_promoted_replay`. Elle ne regarde pas le
byte cible attendu comme predicteur; elle mesure si le `known_mask` ou les
voisins deja connus fournissent un etat corpus exploitable.

```text
output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/index.html
output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/candidates.csv
```

Etat courant:

```text
Fixture matched slots: 320
Target known slots: 0 / 320
Source known slots: 125 / 320
Target exact slots: 0
Best prerequisite target: mid:a / target_source_known_seq = 21 correct / 15 false
Combined prerequisite-state best: 21 correct / 19 false
Combined false-free slots: 0
Promotion-ready bytes: 0
```

Conclusion: le replay promu couvre les offsets dans son mask mais ne debloque
aucun des bytes cible `gradient_like`; les voisins connus donnent seulement un
indice bruite. La suite doit chercher un unlock payload/corpus plus amont, pas
un selecteur d'exception supplementaire.

La passe dependances source exceptions low remonte alors au `source_profile`
effectif de ces 320 slots. Elle calcule l'offset source reel
`source_profile_offset + relative_offset`, verifie si la source est deja connue
dans le replay formule ou directement disponible dans `segment_gap`, puis
construit les aretes quand cette source pointe vers un autre slot high-safe.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_dependency/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency/edges.csv
```

Etat courant:

```text
Source available slots: 157 / 320
Source unknown slots: 163
Unknown source in high-safe graph: 101
Unknown source outside high-safe graph: 62
Exception source unknown slots: 38
Exception source unknown in high-safe graph: 24
Dependency edges: 12
Top unknown dependency edge: 78|195->80|204 = 28 slots
Promotion-ready bytes: 0
```

Conclusion: l'unlock amont est maintenant localise. Une partie du blocage est
un graphe high-safe interne a resoudre avant de revenir aux lows minoritaires;
le reste depend encore de sources externes au sous-graphe.

La passe chaines source exceptions low suit ensuite chaque dependance
`unknown_source` interne au graphe high-safe jusqu'a son terminal. Elle verifie
s'il existe des cycles, puis teste les lows terminaux avec les bytes source
deja disponibles.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_chain/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_chain/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_chain/chains.csv
output/tex_gradient_sequence_high_safe_low_exception_source_chain/terminals.csv
output/tex_gradient_sequence_high_safe_low_exception_source_chain/candidates.csv
```

Etat courant:

```text
Unknown high-safe source chains: 101
Unique terminal slots: 43
Cycle chains: 0
Terminal known-source chains: 86
Terminal unknown-outside chains: 15
Max chain length: 3
Best terminal model: source_low_rel4 = 4 correct / 8 false
Best terminal false-free slots: 0
Promotion-ready bytes: 0
```

Conclusion: le graphe high-safe est acyclique, mais les terminaux ne se
resolvent pas par propagation low/source locale. La suite doit chercher un
unlock externe des terminaux, pas propager directement les lows.

La passe terminaux source exceptions low teste alors les contextes externes des
43 slots terminaux. Elle combine jusqu'a trois champs de contexte et valide les
predictions en leave-one-row-out, sans promouvoir automatiquement les bytes.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal/terminals.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal/candidates.csv
```

Etat courant:

```text
Terminal slots: 43
Feature sets: 1159
Best terminal context: rel_mod4+control_low+low_bucket = 13 correct / 3 false
Best false-free terminal context: target_mod32+terminal_state+low_bucket = 10 slots
Combined false-free slots: 10
Promotion-ready bytes: 0
```

Conclusion: il existe maintenant une piste terminale faux-free mais encore
etroite. La suite doit relire/rejouer ces 10 slots avant toute promotion.

La passe revue terminaux source exceptions low projette ensuite ces 10
terminaux faux-free sur les chaines racines. Elle mesure seulement le replay
avec les deltas de dependance deja observes; ce replay reste oracle et ne
declenche donc aucune promotion.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/terminals.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/chains.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/groups.csv
```

Etat courant:

```text
Predicted terminal slots: 10 / 43
Covered chains: 28
Covered root slots: 28
Covered contexts: 5
Covered chain lengths: 23 length-2 / 5 length-3
Oracle delta replay: 28 exact / 0 false
Promotion-ready bytes: 0
```

Conclusion: la piste terminale explique 28 racines si les deltas de dependance
sont deja connus, mais cette etape est encore une validation oracle. La suite
doit deriver une regle de delta non-oracle avant de rejouer/promouvoir ces
racines.

La passe delta terminaux source exceptions low teste ensuite des contextes
non-oracle pour predire `source_low_delta` sur les aretes high-safe, puis mesure
directement combien des 28 chaines de la revue terminale deviennent rejouables.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/chains.csv
```

Etat courant:

```text
Edge rows: 157
Review chains: 28
Review edges: 28
Feature sets: 17343
Best delta replay: rel_mod4+fragment_low+source_control_low = 6 exact / 1 false
Best false-free delta replay: target_y_mod8+fragment_low+source_control_low = 3 exact
Promotion-ready bytes: 0
```

Conclusion: les contextes non-oracle actuels ne generalisent pas le replay
terminal. La meilleure couverture brute est bruitee, et le meilleur faux-free
ne couvre que 3 racines; il faut chercher des features de delta plus fortes
avant de promouvoir cette piste.

La passe contexte chaines terminaux source exceptions low teste ensuite un
predictor direct du low racine sur les 28 chaines de la revue terminale. Elle
exclut les buckets low racine, trop proches du low cible, et combine le contexte
terminal, la signature du chemin et les features racine/arete.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/chains.csv
```

Etat courant:

```text
Chain rows: 28
Feature sets: 34279
Best chain context: terminal_source_low+edge1_rel_mod4+edge1_gradient_class = 10 correct / 7 false
Best false-free chain context: root_target_x_mod32+root_shape_len_key = 6 chains
Promotion-ready bytes: 0
```

Conclusion: le replay direct de chaine donne une meilleure borne faux-free que
le delta arete par arete, mais il reste trop etroit pour promouvoir. La suite
doit chercher un support terminal/chaine plus large ou un contexte de delta
moins bruite.

La passe support replay terminaux source exceptions low rejoue ensuite tous les
contextes terminaux candidats dans les chaines high-safe avec les deltas de
dependance observes. Elle separe les contextes qui utilisent `low_bucket` des
contextes sans bucket, afin de ne pas confondre support large et indice trop
proche du low cible.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/chains.csv
```

Etat courant:

```text
Terminal contexts: 1159
Chain rows: 101
Best terminal replay: rel_mod8+terminal_state+low_bucket = 34 exact / 35 false
Best false-free terminal replay: target_mod32+terminal_state+low_bucket = 28 chains
Best no-bucket terminal replay: source_availability+target_mod32+root_chains = 24 exact / 6 false
Best no-bucket false-free replay: target_mod32+best_fixed_transition_source_low+root_chains = 6 chains
Promotion-ready bytes: 0
```

Conclusion: elargir les contextes terminaux augmente la couverture seulement au
prix de nombreux faux. Sans `low_bucket`, le meilleur replay faux-free reste a
6 chaines; la suite doit chercher un support terminal non-bucket plus large ou
revenir a une source de delta moins bruitee.

La passe union replay terminaux source exceptions low combine ensuite les
candidats faux-free sans `low_bucket` issus du replay terminal et du contexte
direct de chaine. Elle ajoute les candidats par gain de couverture sans conflit
de prediction, mais garde le resultat en revue parce qu'il s'agit d'une union de
selecteurs etroits.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/selected.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/roots.csv
```

Etat courant:

```text
Candidate rows: 1755
Selected candidates: 9
Covered roots: 25
Chain-context candidates: 1743
Terminal-replay candidates: 12
Conflict roots: 0
Promotion-ready bytes: 0
```

Conclusion: l'union sans conflit couvre 25 racines high-safe, ce qui est la
meilleure piste locale actuelle, mais elle reste trop fragmente pour une
promotion directe. La suite doit deriver un garde plus large ou transformer ces
selecteurs en replay verifiable.

La passe garde union replay terminaux source exceptions low scanne ensuite les
features stables deja calculees pour isoler les racines couvertes par l'union
sans inclure de racines hors union. Elle mesure la compacite de cette garde
avant toute promotion.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/contexts.csv
```

Etat courant:

```text
Union roots: 25
Feature sets: 7175
Candidate rows: 6518
Best full-cover guard: 25 roots / 21 contexts
Best compact guard: 19 roots / 9 contexts
Full-cover candidates: 621
Promotion-ready bytes: 0
```

Conclusion: une garde exacte existe, mais elle reste trop fragmentee
(`21` contextes pour `25` racines) pour servir de promotion robuste. Avec le
seuil compact actuel (`9` contextes), la meilleure garde ne couvre que `19`
racines; la suite doit analyser les 6 misses ou trouver un signal plus stable
que `terminal_context+root_target_y_mod8+root_shape_start_key`.

La passe split garde union replay reprend alors la meilleure garde compacte
(`terminal_context+root_gradient_class`), isole ses trois groupes mixtes et
cherche un champ additionnel capable de couvrir les 6 misses sans faux. Le
meilleur split ajoute `root_length_mod16`.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/misses.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/contexts.csv
```

Etat courant:

```text
Base guard: 19 roots / 9 contexts
Miss roots: 6
Best split: 6 roots / 5 contexts
Combined guard: 25 roots / 14 contexts
Promotion-ready bytes: 0
```

Conclusion: le split reduit fortement la fragmentation (`14` contextes au lieu
de `21`) et couvre toutes les racines de l'union, mais reste au-dessus du seuil
compact de `9` contextes. La suite doit reduire ces 5 contextes additionnels ou
transformer la garde deux niveaux en replay verifie avant promotion.

La passe couverture garde union replay resout ensuite le probleme comme un
set-cover de contextes purs. Apres deduplication et suppression des contextes
domines, elle trouve une couverture complete en `8` contextes, donc sous le
seuil compact de `9`.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/items.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/selected.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/roots.csv
```

Etat courant:

```text
Candidate rows: 37
Selected contexts: 8
Covered roots: 25/25
Promotion candidate bytes: 25
Promotion-ready bytes: 0
```

Conclusion: les 25 racines couvertes par l'union disposent maintenant d'une
garde compacte pure. Ce n'est pas encore une promotion, car il faut convertir
ces 8 contextes en replay garde et revalider l'application aux bytes, mais la
roadmap peut maintenant suivre une piste de promotion candidate au lieu d'une
simple revue fragmentee.

La passe promotion couverture garde union replay applique cette garde compacte
sur les buffers de base `palette_formula_replay`. Elle verifie pour chaque byte
le masque connu, les plages rejetees, les chevauchements, le byte attendu et le
byte predit avant d'ecrire.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/fixtures.csv
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/promotions.csv
```

Etat courant:

```text
Promoted rows: 25/25
Added guard bytes: 25
False bytes: 0
Promotion-ready bytes: 25
Issue rows: 0
```

Conclusion: les 25 bytes de la garde compacte sont maintenant promus proprement
dans un replay separe. La passe suivante consomme ce replay comme nouvelle base
gradient et mesure le deblocage reel des dependances source.

La passe dependances source base replay promue relance `source_dependency` en
utilisant ce replay promu comme fixtures d'entree. Elle mesure donc l'effet
reel des 25 bytes ajoutes sur le graphe high-safe, sans changer les probes
amont ni creer de dependance circulaire dans la pipeline.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/edges.csv
```

Etat courant:

```text
Source available slots: 164/320
Source unknown slots: 156
Unknown high-safe source slots: 94 (101 avant replay promu)
Unknown outside source slots: 62
Top unknown edge: 78|195->80|204 (22 slots, 28 avant replay promu)
Issue rows: 0
```

Conclusion: le replay promu est maintenant consomme par une passe aval et
debloque 7 sources high-safe, dont 2 sources inconnues d'exception. La piste
suivante reste la resolution des 94 dependances high-safe restantes, avec le
top edge `78|195->80|204` reduit a 22 slots.

La branche base replay promue relance ensuite les chaines, terminaux, support
replay et union sur ces `slots.csv` consommes. La couverture garde obtenue sur
la base promue couvre les 20 racines restantes de cette branche, puis la
seconde promotion applique uniquement les bytes encore inconnus de la base
precedente.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_base/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/summary.csv
```

Etat courant:

```text
Promoted-base cover: 20/20 roots
Second promoted rows: 4/20
Second added guard bytes: 4
Second false bytes: 0
Second issue rows: 0
Source available slots after second replay: 165/320
Unknown high-safe source slots: 93 (94 avant second replay)
Top unknown edge: 78|195->80|204 (21 slots, 22 avant second replay)
```

Conclusion: la seconde promotion est propre mais marginale: elle ajoute 4
bytes, dont 1 source high-safe utile au graphe. Une tentative de troisieme
promotion sur la meme couverture n'ajoute plus aucun byte; la suite doit donc
attaquer les 93 dependances high-safe restantes avec un autre signal.

La revue du noyau residuel classe ces 93 dependances high-safe par edge et par
terminal de chaine. Elle separe les racines qui terminent sur une source connue
des racines bloquees par une source externe encore inconnue, afin d'eviter de
relancer indefiniment la meme promotion saturee.

```text
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/edges.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/terminals.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/roots.csv
```

Etat courant:

```text
Unknown high-safe slots: 93
Dependency edges: 12
Terminal slots: 39
Terminal known chains: 83
External terminal chains: 10
Top unknown edge: 78|195->80|204 (21 slots)
Dominant blocker: resolve external terminal source bytes
Issue rows: 0
```

Conclusion: les edges 1 a 3 restent bloques par des terminaux externes
inconnus, alors que les autres edges demandent une meilleure transform
terminale depuis des sources connues. La prochaine piste doit donc cibler les
bytes sources externes terminaux ou une transform terminale plus forte, pas une
troisieme promotion de la meme couverture.

La revue des sources terminales externes recalcule les spans inconnus depuis la
seconde base promue et rattache les 7 bytes sources externes aux terminaux qui
bloquent le noyau residuel:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/bytes.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/spans.csv
```

Etat courant:

```text
External terminal bytes: 7
Blocked root chains: 10
Blocker spans: 3
Blocker span bytes: 9
Small nonzero blocker spans: 3
Top blocker span: 80:7-12 (4 chains, expected 5554555356)
Other blocker spans: 80:0-3 (6a6c6a), 58:9-10 (33)
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le blocage externe n'est plus un grand span ambigu apres la seconde
promotion. Il se reduit a trois petits spans non-zero (`80:7-12`, `80:0-3`,
`58:9-10`). La prochaine piste concrete est donc un selecteur small unresolved
nonzero cible sur ces spans, avec validation avant promotion.

La sonde du selecteur small non-zero externe compare ces trois spans aux gaps
courts deja connus, puis teste des fenetres source non-oracle:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/source_candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/context_candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv
```

Etat courant:

```text
Target spans: 3
Target bytes: 9
Joined target spans: 3
Small gap rows: 188
Known small gaps: 15
False-free contexts: 0
Full source candidate spans: 1
Covered target bytes: 1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le span `58:9-10` a des candidats source triviaux sur un seul
octet, mais les spans `80:0-3` et `80:7-12` ne sont pas couverts par une source
non-oracle fiable. La prochaine piste concrete devient la grammaire
compact-control des petits gaps non-zero externes, pas une promotion directe.

La sonde compact-control locale teste des slices, repetitions et motifs `ABA`
autour de `control_ref_offset`, puis rejette les candidats qui contredisent les
gaps courts deja connus:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/groups.csv
```

Etat courant:

```text
Target bytes: 9
Known reference rows: 15
Full target match bytes: 4
Guarded full match bytes: 0
Rejected full-match spans: 2
Neighbor value cover bytes: 9
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: la copie compact-control directe explique seulement des candidats
locaux rejetes (`80:0-3`, `58:9-10`). Le span `80:7-12` n'a pas de sortie
deterministe, mais tous ses octets sont dans l'alphabet voisin elargi. La
prochaine piste concrete est donc l'ordre spatial/gradient de ces valeurs
compact-control locales.

La sonde de pont spatial/gradient cherche une ancre deja connue autour de chaque
span externe, puis encode le span comme petites deltas signees depuis cette
ancre:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/signatures.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/known_signatures.csv
```

Etat courant:

```text
Target bytes: 9
Anchor-supported bytes: 9
Target signature seen bytes: 1
Known signature rows: 17
Repeated known signatures: 2
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: tous les octets externes ont une explication spatiale locale:
`80:0-3` utilise l'ancre droite `6b` avec la signature `-1,+1,-1`,
`80:7-12` utilise l'ancre gauche `56` avec `-1,-2,-1,-3,0`, et `58:9-10`
reprend une signature connue sur un seul octet. Les deux signatures du frontier
`80` restent uniques; cela motive un selecteur non-oracle pour ces signatures,
avant toute promotion.

La sonde de selecteur du pont spatial regroupe les candidats d'ancre par
familles non-oracle (`literal_edge_anchor`, `op_length_anchor`,
`control_mod_anchor`, etc.), puis verifie si une famille deja vue sur des spans
connus predit les signatures cible:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/selectors.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/candidates.csv
```

Etat courant:

```text
Target bytes: 9
Target candidate rows: 5
Known candidate rows: 17
Selector group rows: 154
Guarded exact bytes: 0
Frontier 80 target-only unique bytes: 8
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les 8 bytes du frontier `80` sont bien isoles par des signaux
non-oracle locaux (`literal_edge_anchor` autour des ancres `6b` et `56`), mais
aucun groupe equivalent n'existe encore dans les references connues. La
prochaine piste concrete n'est donc pas une promotion; il faut deriver le
producteur compresse/controle des deltas `-1,+1,-1` et `-1,-2,-1,-3,0`.

La sonde producteur delta teste ensuite des slices et motifs `ABA` du segment
compresse autour de `control_ref`, en sortie valeur directe ou delta depuis
l'ancre spatiale:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/producers.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/candidates.csv
```

Etat courant:

```text
Target spans: 2
Target bytes: 8
Compact exact bytes: 3
Compact guarded exact bytes: 0
Compact rejected bytes: 3
Compact missing bytes: 5
Target-only template bytes: 8
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: `80:0-3` a des producteurs compacts exacts, dont le motif deja
connu `seg_ref@-8,-11:aba:identity`, mais ces producteurs restent rejetes par
les references connues. `80:7-12` n'a toujours pas de producteur compact/control
exact; il ne reste pour lui que le template spatial cible `56 + [-1,-2,-1,-3,0]`.
La prochaine piste concrete est donc d'etendre le producteur compact/control du
pont cinq octets `80:7-12`.

La sonde combinator cinq octets teste ensuite des compositions locales entre
l'ancre spatiale et deux bytes du segment compresse (`seg_ref+2`, `seg_ref+3`):

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/templates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/diagnostics.csv
```

Etat courant:

```text
Target spans: 1
Target bytes: 5
Compact exact bytes: 5
Known reference len5 rows: 0
Diagnostic eval rows: 12
Diagnostic false rows: 9
Diagnostic false spans: 1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: `80:7-12` est reconstruit par le combinator compact
`anchor-1, seg_ref+3, anchor-1, seg_ref+2, anchor` avec `anchor=56`,
`seg_ref+2=53` et `seg_ref+3=54`. Le meme type de template produit cependant
des faux sur le span diagnostic `21:281-286`, et aucune reference connue de
longueur 5 ne permet encore une garde de promotion. La prochaine piste concrete
est donc une garde non-oracle qui separe le pont cinq octets du frontier `80`
du faux diagnostic `21:281-286`.

La sonde de garde cinq octets classe ensuite les signaux non-oracle qui
conservent `80:7-12` tout en rejetant les faux diagnostics:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/guards.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/diagnostics.csv
```

Etat courant:

```text
Target bytes: 5
Diagnostic false rows: 9
Diagnostic false spans: 1
Diagnostic false-free guard rows: 10
Compact/control guard rows: 4
Best guard: compact_pair_control
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: la meilleure garde diagnostique est
`gap_role=between_literal_zero | span_length=5 | control_ref_mod64=22 |
anchor_rel=-2 | segment_pair=5354`. Elle rejette les 9 faux diagnostics et
garde le pont `80:7-12`, mais elle manque encore de support connu/reference
pour etre promue. La prochaine piste concrete est donc de trouver un support
connu ou reference pour cette garde cinq octets.

La sonde de support cinq octets cherche ensuite cette garde dans tout le corpus
d'operations pour verifier si elle existe hors cible ou sur des bytes deja
connus:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/support.csv
```

Etat courant:

```text
Operation rows: 984
Length5 operation rows: 72
Length5 gap rows: 22
Guard candidate rows: 1
Guard known-full rows: 0
Guard reference exact rows: 1
Same-guard non-target rows: 0
Target-only reference bytes: 5
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le corpus d'operations complet ne donne aucun support connu ni
non-cible pour la garde cinq octets. Le seul support exact est la reference
cible `80:7-12`; il faut donc reviser ce support target-only avant tout replay
ou promotion.

La revue target-only de cette garde relache ensuite les features une par une et
par combinaisons pour verifier si un sous-ensemble donne un support non-cible
fiable:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/features.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/ablations.csv
```

Etat courant:

```text
Support rows: 125
Full guard rows: 1
Full guard known-full rows: 0
Full guard non-target rows: 0
Exact non-target rows: 0
Known exact rows: 0
Known false rows: 111
Unique single features: 2 (control_ref_mod64, segment_pair)
Relaxed known rows: 111
Relaxed false rows: 124
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: `control_ref_mod64=22` et `segment_pair=5354` isolent deja la cible
`80:7-12` seuls dans le corpus d'ancres longueur 5. Les relachements qui
touchent des bytes connus produisent des faux, donc la garde reste bloquee par
des features target-only. La prochaine piste concrete est de chercher une
evidence non-cible independante pour le pont cinq octets du frontier `80`.

La sonde d'evidence independante sort ensuite du corpus d'operations et scanne
directement les segments et les fenetres attendues du manifest:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence/segment_hits.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence/formula_windows.csv
```

Etat courant:

```text
Manifest rows: 32
Fixture rows: 32
Segment positions scanned: 65570
Pair any rows: 1
Pair+mod rows: 1
Pair+mod non-target rows: 0
Formula windows: 74
Formula exact rows: 1
Formula exact non-target rows: 0
Formula known-full exact rows: 0
Formula known-full false rows: 36
Target-only exact rows: 1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: meme sans segmentation, le couple `segment_pair=5354` avec
`control_ref_mod64=22` n'apparait qu'une fois dans le manifest, sur
`80:7-12`. La formule ne donne aucun exact non-cible et aucun exact connu; la
prochaine piste concrete est donc d'elargir la recherche d'evidence au-dela du
corpus de fixtures courant.

La sonde de corpus etendu regenere ensuite les fixtures depuis toute la file
gap-rule, puis rescane le meme couple/garde sur les fenetres attendues:

```text
output/tex_gap_rule_fixtures_expanded/index.html
output/tex_gap_rule_fixtures_expanded/manifest.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/hits.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/windows.csv
```

Etat courant:

```text
Manifest rows: 105
Segment positions scanned: 4386930
Pair any rows: 323
Pair+mod rows: 3
Pair+mod non-target rows: 2
Reference window rows: 11171
Reference exact rows: 1
Reference exact non-target rows: 0
Target-only exact rows: 1
Pair+mod non-target frontiers: 5,104
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le corpus etendu trouve deux lignes non-cibles avec
`segment_pair=5354` et `control_ref_mod64=22` (`frontier_id=5` et `104`), mais
la formule exacte reste limitee au span cible `80:7-12`. La prochaine piste
concrete est donc d'inspecter ces deux lignes `pair+mod` non-cibles pour trouver
une garde alternative qui generalise sans promouvoir une regle target-only.

La revue pair-mod inspecte ensuite les 323 occurrences `segment_pair=5354` du
corpus etendu et classe les features non-oracle qui gardent la cible tout en
rejetant les deux faux avec `control_ref_mod64=22`:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/hit_features.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/features.csv
```

Etat courant:

```text
Pair any rows: 323
Pair+mod rows: 3
Pair+mod non-target rows: 2
Feature rows: 27
Pair+mod false-free feature rows: 23
Best refined guard: rule_type=compact_control_stream
Best pair+mod rows: 1
Best pair+mod non-target rows: 0
Best pair any rows: 4
Best pair any non-target rows: 3
Best pair any frontiers: 29,54,55,80
Target-only refined rows: 1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le raffinement le plus sain ajoute
`rule_type=compact_control_stream` a la garde cinq octets. Cette feature rejette
les deux faux `pair+mod` et reste plus large qu'une signature de bytes locale
puisqu'elle apparait aussi avec le couple `5354` sur les frontiers `29`, `54` et
`55`. Sous modulo `22`, elle reste toutefois target-only: la prochaine piste
concrete est donc de chercher un support independant pour ce raffinement
compact-control avant toute promotion.

La sonde de support raffine teste ensuite ce guard
`rule_type=compact_control_stream` sur les quatre hits compact-control du couple
`5354`:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/hits.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/windows.csv
```

Etat courant:

```text
Refined guard: rule_type=compact_control_stream
Refined pair rows: 4
Refined non-target rows: 3
Refined pair+mod rows: 1
Refined pair+mod non-target rows: 0
Reference window rows: 1457
Reference exact rows: 1
Reference exact non-target rows: 0
Target-only exact rows: 1
Non-target frontiers: 29,54,55
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les frontiers `29`, `54` et `55` confirment que le raffinement n'est
pas une signature cible unique, mais la formule `anchor-1, seg_ref+3, anchor-1,
seg_ref+2, anchor` ne matche toujours qu'en cible. La prochaine piste concrete
est donc de deriver une variante de formule pour les lignes compact-control
non-cibles avant de reconsiderer la promotion du guard cinq octets.

La sonde de variante formule separe ensuite les candidats locaux, proches du
couple `5354`, des candidats plein-gap/tail sur les quatre hits compact-control:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/variants.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/matches.csv
```

Etat courant:

```text
Refined pair rows: 4
Refined non-target rows: 3
Local variant rows: 106
Local multi-frontier rows: 106
Local all non-target rows: 0
Local target rows: 12
Full variant rows: 4395
Full all non-target rows: 113
Full target rows: 473
Best local template: ar+2|c55|s+2+0|a+0|c00|c00
Best local samples: 80:9-14:5553560000;29:8-13:5553550000
Best full template: ar+0|a+0|s+1+0|c53|c54|s+4+0
Best full frontiers: 29,54,55
Best full samples: 29:586-591:6854535457;54:283-288:5555535454;55:276-281:6caa535459
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: aucune variante locale ne couvre les trois non-cibles
compact-control. Les variantes qui couvrent `29`, `54` et `55` existent
uniquement dans les fenetres plein-gap/tail et doivent donc etre gatees par leur
contexte local/tail avant toute promotion.

La sonde gate contexte tail classe ensuite les 113 variantes plein-gap qui
couvrent les trois non-cibles compact-control:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate/contexts.csv
```

Etat courant:

```text
Formula variant rows: 4395
Full all non-target rows: 113
Gated candidate rows: 113
Tail-only candidate rows: 113
Non-tail candidate rows: 0
Local-context candidate rows: 0
Target-overlap candidate rows: 0
Unique tail distance groups: 2
Best tail template: ar+0|a+0|s+1+0|c53|c54|s+4+0
Best tail distances: 27,9,15
Best ref distances: 501,244,241
Best samples: 29:586-591:6854535457;54:283-288:5555535454;55:276-281:6caa535459
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les 113 candidats plein-gap sont tous bloques comme `tail_only`:
aucun ne revient pres du `ref_offset`, aucun ne touche le contexte local, et
aucun ne recoupe la cible. La prochaine piste concrete est donc de chercher un
support formule cinq octets non-tail, plutot que de promouvoir ces coincidences
de queue.

La sonde support non-tail filtre ensuite les variantes formule non-nulles qui
ont au moins un match hors queue:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/groups.csv
```

Etat courant:

```text
Formula variant rows: 4501
Non-tail support rows: 2744
Non-tail all non-target rows: 0
Non-tail partial non-target rows: 2681
Non-tail target+non-target rows: 63
Local nonzero rows: 2
Dominant partial group: 29,54
Dominant partial rows: 2661
Best local template: ar+1|s+5+0|a+0|a+0|a-2|a-2
Best local frontiers: 55
Best partial template: ar+0|a+0|a+0|s+5+2|s+5+2|s+5+2
Best partial frontiers: 29,54
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le support non-tail existe, mais il reste en familles partielles:
la plus forte relie `29` et `54`, deux lignes locales non-nulles relient la
cible a `55`, et aucune formule non-tail ne couvre simultanement `29`, `54` et
`55`. La prochaine piste concrete est donc de splitter ce support par famille de
frontiers avant de chercher une promotion.

La sonde split familles pair regroupe ensuite ce support non-tail par frontiers
non-cibles et mesure les recouvrements exacts entre familles:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/families.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/overlaps.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/atoms.csv
```

Etat courant:

```text
Non-tail support rows: 2744
Family rows: 5
Partial family rows: 3
Target-overlap family rows: 1
Local family rows: 1
All non-target family rows: 0
Required non-target frontiers: 29,54,55
Dominant family: 29,54
Dominant family rows: 2661
Dominant family missing frontiers: 55
Weak pair families: 29,55;54,55
Exact template overlap rows: 1
Shape overlap rows: 21
Cross-family exact all non-target rows: 0
Best exact overlap template: s+5+0|a+0|a+0|a-2|a-2
Best exact overlap families: 29,55;55
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le split confirme que la famille dominante `29,54` ne touche pas
`55`, tandis que les familles `29,55` et `54,55` restent faibles. Le seul
recouvrement exact de template relie `55` et `29,55`, pas `29,54,55`. La piste
concrete suivante est donc de deriver un pont entre la famille dominante
`29,54` et le frontier manquant `55`.

La sonde pont familles isole ensuite les recouvrements de forme qui couvrent
l'union non-cible `29,54,55`:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/bridges.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/examples.csv
```

Etat courant:

```text
Required non-target frontiers: 29,54,55
Dominant family: 29,54
Dominant family missing frontiers: 55
Shape bridge rows: 8
Target-free shape bridge rows: 4
Target-overlap shape bridge rows: 4
Exact bridge rows: 0
Dominant-to-missing shape rows: 8
Dominant-to-missing target-free rows: 4
Best shape bridge: s|s|a|s|s
Best shape bridge families: 29,54;29,55
Best shape bridge candidate rows: 137
Best exact overlap template: s+5+0|a+0|a+0|a-2|a-2
Best exact overlap frontiers: 29,55
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: quatre ponts de forme target-free existent, mais aucun n'est encore
un template exact. Le meilleur pont `s|s|a|s|s` relie la famille dominante
`29,54` a `29,55` sans recouper la cible. La prochaine piste concrete est donc
de deriver un resolveur d'atomes pour ces ponts de forme avant toute promotion.

La sonde resolveur d'atomes classe ensuite les positions internes de ces ponts
target-free:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/shapes.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/atoms.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/positions.csv
```

Etat courant:

```text
Target-free shape bridge rows: 4
Shape resolver rows: 4
Exact family resolver rows: 1
Single-axis resolver rows: 3
Shared ambiguity single-axis rows: 2
Broad ambiguous shape rows: 1
Family atom rows: 40
Resolved family atom rows: 31
Ambiguous family atom rows: 9
Position delta rows: 20
Shared position rows: 12
Divergent exact position rows: 3
Divergent ambiguous position rows: 5
Best exact shape: a|s|s|c|c
Best single-axis shape: a|s|s|c|c
Best single-axis position: 2
Best single-axis switch: 29,54:s+1+0;29,55:s+6+2
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le signal utile est un switch single-axis en position 2, exact sur
`a|s|s|c|c` et partage avec ambiguite controlee sur deux autres formes. Le
grand pont `s|s|a|s|s` reste trop ambigu pour promotion. La prochaine piste
concrete est donc de gater ce switch d'atome contre les templates qui recoupent
la cible.

La sonde de gating target-overlap teste ensuite si ce switch single-axis est
directement porte par les templates qui recoupent la cible:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/gates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/families.csv
```

Etat courant:

```text
Switch position: 2
Switch map: 29,54:s+1+0;29,55:s+6+2
Target-overlap shape rows: 4
Switch-applicable shape rows: 1
Exact switch shape rows: 0
Loose switch shape rows: 1
Target direct switch rows: 0
Target indirect switch rows: 1
Shape mismatch rows: 3
Best switch shape: a|s|s|s|s
Best switch shape verdict: target_overlap_switch_indirect_only
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le switch existe bien dans une forme target-overlap, mais seulement
en support indirect: la cible est portee par la famille `29`, tandis que le
switch mesure `29,54` contre `29,55`. La prochaine piste concrete est donc de
splitter le target-overlap par famille porteuse avant toute promotion.

La sonde split carrier-family separe ensuite les familles qui portent la cible
des familles qui portent le switch:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/splits.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/carriers.csv
```

Etat courant:

```text
Switch position: 2
Switch map: 29,54:s+1+0;29,55:s+6+2
Target-overlap shape rows: 4
Carrier split rows: 4
Target carrier family rows: 5
Switch support family rows: 2
Direct carrier switch rows: 0
Indirect carrier split rows: 1
Carrier shape mismatch rows: 3
Target switch mismatch family rows: 1
Best carrier shape: a|s|s|s|s
Best target carriers: 29
Best carrier atom sets: 29:s-4+0,s-4-1
Best switch support: 29,54;29,55
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: la seule piste compatible avec la position 2 est un split indirect:
la cible `29` a ses propres atomes `s-4+0/s-4-1`, tandis que le support switch
reste sur `29,54` et `29,55`. La prochaine piste concrete est donc de deriver
un switch local a la famille porteuse `29`.

La sonde switch local carrier inspecte ensuite les templates de la famille
porteuse `29` pour la forme `a|s|s|s|s`:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/candidates.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/samples.csv
```

Etat courant:

```text
Carrier shape: a|s|s|s|s
Target carrier: 29
Switch position: 2
Carrier candidate rows: 2
Carrier target rows: 3
Carrier non-target rows: 2
Carrier switch atom rows: 2
Carrier switch atoms: s-4+0;s-4-1
Target switch atom rows: 2
Non-target switch atom rows: 2
Shared target/non-target atom rows: 2
Target-only switch atom rows: 0
Best target atom: s-4+0
Best target template: ar+0|a+0|s-4+0|s-3+0|s-4-1|s-4-2
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: les deux atomes carrier-local `s-4+0` et `s-4-1` restent partages
entre samples cible et non-cible. Il faut donc splitter le contexte local de la
famille `29` avant de promouvoir quoi que ce soit.

La sonde split contexte carrier-local teste ensuite les seuils simples de
position sur ces samples:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/splits.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/samples.csv
```

Etat courant:

```text
Carrier shape: a|s|s|s|s
Target carrier: 29
Switch position: 2
Sample rows: 5
Target sample rows: 3
Non-target sample rows: 2
Target start range: 234..253
Non-target start range: 274..324
Best context: span_start
Best threshold: 253
Best direction: lte
Best correct rows: 3
Best false rows: 0
Best unknown rows: 0
False-free context rows: 1
Best target atoms: s-4+0;s-4-1
Best non-target atoms: s-4+0;s-4-1
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: le seuil `span_start <= 253` separe les trois samples cible des
deux non-cibles sans faux positif. La prochaine piste concrete est de revoir ce
split start-threshold pour promotion eventuelle.

La revue promotion du contexte carrier-local valide ensuite que ce seuil est
non-oracle et que tous les samples attendus sont couverts:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/splits.csv
```

Etat courant:

```text
Threshold support ready rows: 1
Threshold non-oracle rows: 1
Validated target rows: 3
Validated non-target rows: 2
Validated false rows: 0
Validated unknown rows: 0
Promotion candidate bytes: 5
Promotion-ready bytes: 5
Issue rows: 0
```

Conclusion: le seuil `span_start <= 253` est pret pour promotion. La prochaine
piste concrete est de promouvoir ce split start-threshold carrier-local dans le
replay compact-control cinq octets.

La promotion carrier-local applique ensuite ce garde sur le span cible
`80:7-12` et ajoute la sortie compact-control `5554555356` dans la base de
fixtures promue:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/targets.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/bytes.csv
```

Etat courant:

```text
Target rows: 1
Promoted rows: 1
Context candidate bytes: 5
Context added bytes: 5
Context exact bytes: 5
Context false bytes: 0
Skipped known bytes: 0
Skipped rejected bytes: 0
Total clean bytes: 9787
Remaining unresolved bytes: 7659
Promotion-ready bytes: 5
Issue rows: 0
```

Conclusion: le replay promu carrier-local remplit les offsets `7..11` de
`dinodead.pcx` frontier `80` sans conflit. La prochaine piste concrete est de
consommer cette base promue comme nouvelle base gradient.

La sonde de dependances source consomme ensuite cette base promue pour mesurer
l'effet sur les slots exceptions:

```text
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/slots.csv
```

Etat courant:

```text
Slots: 320
Exception slots: 86
Source available slots: 170
Source unknown slots: 150
Source unknown in high-safe slots: 93
Source unknown outside high-safe slots: 57
Exception source unknown slots: 33
Exception source unknown in high-safe slots: 22
Exception source unknown outside high-safe slots: 11
Top unknown dependency edge: 78|195->80|204
Top unknown dependency edge slots: 21
Promotion-ready bytes: 0
Issue rows: 0
```

Conclusion: la base carrier-context promue ajoute cinq sources disponibles
(`165 -> 170`) et reduit les exceptions source unknown (`36 -> 33`), mais le
noyau high-safe reste bloque a `93` sources inconnues. La prochaine piste
concrete est de resoudre ces dependances high-safe restantes.

Le coeur residuel carrier-context a isole des terminaux externes encore
bloquants. La garde `delta_producer` valide le span `80:0-3` par le producteur
`seg_abs@1,22:aba:low2_signed` et une garde non-oracle
`span_length=3|anchor_side=right`, `anchor_rel <= 9`.

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay/targets.csv
```

Etat de la garde:

```text
Rejected target bytes: 3
Guard rows: 292
False-free guard rows: 100
Best target span: 80:0-3
Best selector: seg_abs@1,22:aba:low2_signed
Best known exact rows: 5
Best known false rows: 0
Best rejected false rows: 1
Promotion-ready bytes: 3
Issue rows: 0
```

Le replay promu applique ces trois octets sur la base carrier-context:

```text
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv
```

Etat du replay promu:

```text
Target rows: 1
Guard candidate bytes: 3
Guard added bytes: 3
Guard exact bytes: 3
Guard false bytes: 0
Total clean bytes: 9790
Promotion-ready bytes: 3
Issue rows: 0
```

La consommation source-dependency de cette base montre le gain reel:

```text
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/index.html
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/summary.csv
output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_residual_core/index.html
output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_delta_guard_promoted_replay/index.html
```

Etat apres promotion delta-guard:

```text
Source available slots: 173
Source unknown slots: 147
Source unknown in high-safe slots: 93
Source unknown outside high-safe slots: 54
Exception source unknown slots: 32
Terminal known chains: 90
Terminal unknown outside chains: 3
Remaining external blocker: 58:9-10
```

Conclusion: la promotion delta-guard ajoute trois sources disponibles
(`170 -> 173`) et reduit les chaines terminales externes (`6 -> 3`). Le dernier
blocker terminal externe est le span `58:9-10` (`33`), couvert par
`control_prefix@5:add_const=02`; la prochaine piste concrete est de revoir ce
source candidate avant promotion gardee.

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

Une passe post-formula verifie ensuite si les nouveaux octets connus ouvrent
des copies verticales source-connue a distance 320 sur les cibles encore
inconnues:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe/candidates.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe/rules.csv
```

Etat courant:

```text
Source-known unknown slots: 197
Copy-exact bytes: 22
Copy-false bytes: 175
Copy precision: 0.111675
Best false-free repeated feature set: x_bucket32 + y + offset_mod16
Best false-free repeated bytes: 5
Promotion candidate bytes: 0
```

Conclusion: les copies verticales post-formula restent trop bruitees. Les
petits contextes false-free sont positionnels et ne couvrent que 5 bytes au
mieux; aucune promotion de copie verticale n'est sure.

Une passe post-formula supplementaire teste ensuite les copies depuis un pair
gradient de meme forme (`band_shape`, `step_shape`, `gradient_class` ou
`length_band8`) au meme offset relatif, uniquement quand le pair est deja connu
dans le replay palette/formule:

```text
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/index.html
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/candidates.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/families.csv
output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/rules.csv
```

Etat courant:

```text
Unknown gradient slots: 1564
Peer-copy candidates: 573
Copy-exact bytes: 37
Copy-false bytes: 536
Copy precision: 0.064572
Best selector family: length_band8
Best false-free repeated feature set: rel_mod16 + x_mod8 + prediction_low
Best false-free repeated bytes: 5
Promotion candidate bytes: 0
```

Conclusion: les pairs de meme forme ne produisent pas de source gradient
fiable. `length_band8` donne presque tous les candidats mais reste massivement
faux, et le seul contexte false-free est positionnel et limite a 5 bytes. La
prochaine piste gradient doit donc viser un producteur source/profil plus fort,
pas une copie entre formes similaires.

La sonde source-profile high/low reprend ensuite les meilleures fenetres de
profil source, mais les evalue apres le replay palette/formule et en
leave-one-row-out: un slot n'est predit que si les autres lignes du meme
contexte imposent un delta unique.

```text
output/tex_gradient_source_profile_high_low/index.html
output/tex_gradient_source_profile_high_low/slots.csv
output/tex_gradient_source_profile_high_low/rules.csv
```

Etat courant:

```text
Source-profile slots: 1564
Source-profile rows: 29
Feature sets: 2516
Full false-free feature sets: 0
Best full rule: top_nibble + length_band8 + source_byte = 43 exact / 105 false
High false-free feature sets: 38
Best high false-free slots: 108
Best high false-free rule: offset_delta_bucket + length_band8 + source_high + rel_mod4
Best high broad rule: gradient_class + top_nibble + source_high + rel_mod16 = 465 exact / 75 false
Low false-free feature sets: 0
Best low rule: pool + top_nibble + source_byte + rel_mod4 = 46 exact / 86 false
Promotion candidate bytes: 0
```

Conclusion: le source-profile produit un signal partiel utile sur le nibble
haut, mais aucun chemin full-byte ou low-nibble false-free. Il doit donc rester
un indice de phase/etat pour une passe suivante, pas une promotion du decodeur.

La passe focalisee high-safe low applique ensuite la meilleure regle
high-nibble false-free (`offset_delta_bucket + length_band8 + source_high +
rel_mod4`) puis cherche uniquement un resolveur low-nibble dans les slots
ainsi bornes:

```text
output/tex_gradient_source_profile_high_safe_low/index.html
output/tex_gradient_source_profile_high_safe_low/slots.csv
output/tex_gradient_source_profile_high_safe_low/rules.csv
```

Etat courant:

```text
High-safe slots: 108
High-safe rows: 2
Target-low false-free sets: 0
Best target-low rule: rel_mod16 + high_context = 12 exact / 21 false
Delta-low false-free sets: 0
Best delta-low rule: source_byte + rel_mod16 = 10 exact / 20 false
Promotion candidate bytes: 0
```

Conclusion: meme quand le high nibble est borne sans faux, le low nibble reste
bruite et ne couvre que deux lignes. Cette sous-piste doit etre abandonnee au
profit d'un etat gradient plus riche.

La passe macro/source-profile croise ensuite les 1 564 slots source-profile
avec l'etat macro clusterise (phase/opcode/fixture/ancrages) et rejoue les
contextes mixtes jusqu'a 3 features, plus les meilleurs contextes a 4 features
issus du scan large:

```text
output/tex_gradient_macro_source_profile_state/index.html
output/tex_gradient_macro_source_profile_state/slots.csv
output/tex_gradient_macro_source_profile_state/rules.csv
```

Etat courant:

```text
Joined slots: 1564
Source-profile rows: 29
Macro rows: 36
Feature sets: 3264 focused
Full false-free feature sets: 8
Best full false-free slots: 2
Best full rule: macro_fixture_hi_pair + macro_gradient_class + source_high + rel_mod16 = 55 exact / 191 false
Target-low false-free feature sets: 3
Best target-low false-free slots: 2
Best target-low rule: macro_fixture_hi_pair + macro_gradient_class + source_high + rel_mod16 = 74 exact / 183 false
Best low-false target-low rule: macro_next_op_gap + macro_fixture_opcode_pair + source_high = 10 exact / 2 false
Low-delta false-free feature sets: 10
Best low-delta false-free slots: 2
Best low-delta rule: macro_fixture_hi_pair + macro_gradient_class + source_low + rel_mod16 = 63 exact / 171 false
Promotion candidate bytes: 0
```

Conclusion: l'etat macro enrichi confirme seulement des contextes false-free
minuscules (2 slots) et les meilleurs contextes reutilisables restent trop
faux. Cette piste est donc bornee comme sur-apprise; la suite doit chercher un
etat payload/sequence non local plutot qu'une combinaison locale
macro/source-profile.

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

La generalisation residuelle apres adjacent-known borne ensuite le nouvel etat:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization/slots.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization/rules.csv
```

Etat courant:

```text
Selected high slots: 22
Replayable unknown slots: 5
Target already known slots: 15
Blocked prerequisite slots: 2
False-free feature sets: 0
Best correct/false/unknown: 0/1/4
Issue rows: 0
```

Les trois checks residuels ne trouvent plus de candidat:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth/index.html
```

Etat courant:

```text
Residual low-split feature sets: 70375
Residual low-split false-free sets: 0
Residual low-split promotion-candidate bytes: 0
Residual corpus feature sets: 98854
Residual corpus false-free rule sets: 0
Residual corpus promotion-candidate bytes: 0
Fourth adjacent-known candidate/false/conflict slots: 0/0/0
```

Conclusion: les combinaisons low-split, corpus et adjacent-known actuelles sont
epuisees a 9435 bytes propres. Il reste 5 slots sequence replayables et 2 slots
bloques; la prochaine piste doit ajouter une nouvelle famille de features au
dela de corpus/adjacent-known.

La nouvelle famille transform teste ensuite les lows comme transformation des
bytes precedents connus, plutot que comme valeur absolue:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/slots.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/rules.csv
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/index.html
```

Etat courant:

```text
Transform feature sets: 3576
False-free transform sets: 8
Best transform: low_xor_prev1 + dominant
Transform promotion candidates: 1
Promoted transform rows: 1/1
Transform added/exact/false bytes: 1/1/0
Total clean bytes after transform: 9436
Remaining unresolved bytes: 8010
```

La promotion est propre: le slot `row 9 / frontier 22 / offset 2` est promu en
`68` par `low_xor_prev1 + dominant`, sans faux positif ni issue.

Les checks residuels apres cette promotion bornent le nouvel etat:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent/index.html
```

Etat courant:

```text
Post-transform replayable unknown slots: 4
Post-transform target-known slots: 16
Post-transform blocked prerequisite slots: 2
Second transform false-free sets: 0
Residual low-split false-free sets: 0
Residual low-split promotion-candidate bytes: 0
Residual corpus false-free rule sets: 0
Residual corpus promotion-candidate bytes: 0
Residual adjacent-known candidate/false/conflict slots: 0/0/0
```

Conclusion intermediaire: la famille transform selection-only ajoute 1 byte
propre et epuise aussitot ses propres suites simples.

La meme famille appliquee au corpus complet apprend ensuite les transformations
depuis 567 entrees de payload, et non plus seulement depuis les 22 slots high
selectionnes:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/index.html
```

Etat courant:

```text
Corpus-transform training entries: 567
Corpus-transform feature sets per pass: 11844
First corpus-transform false-free/candidates: 69/1
Second corpus-transform false-free/candidates: 8/1
Third corpus-transform false-free/candidates: 61/1
Corpus-transform promoted rows: 3/3
Corpus-transform added/exact/false bytes: 3/3/0
Total clean bytes after corpus-transform: 9439
Remaining unresolved bytes: 8007
```

Les promotions propres sont:

```text
row 0 / frontier 26 / offset 33 -> 6d
row 4 / frontier 80 / offset 53 -> 6d
row 4 / frontier 80 / offset 22 -> 68
```

Les checks residuels apres la troisieme promotion bornent le nouvel etat:

```text
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent/index.html
```

Etat courant:

```text
Final replayable unknown slots: 1
Final target-known slots: 19
Final blocked prerequisite slots: 2
Fourth corpus-transform false-free sets: 0
Residual low-split false-free sets: 0
Residual low-split promotion-candidate bytes: 0
Residual corpus false-free rule sets: 0
Residual corpus promotion-candidate bytes: 0
Residual adjacent-known candidate/false/conflict slots: 0/0/0
```

Conclusion intermediaire: transform selection-only + corpus-transform ajoutent
4 bytes propres apres adjacent-known, portant l'etat a 9439 bytes propres.

La famille low-copy cible ensuite le dernier slot sequence replayable en
validant `low = prev1_low` sur le corpus avec support leave-one-row-out:

```text
output/tex_micro_mixed_value_payload_sequence_low_copy/index.html
output/tex_micro_mixed_value_payload_sequence_low_copy/slots.csv
output/tex_micro_mixed_value_payload_sequence_low_copy/rules.csv
output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/index.html
```

Etat courant:

```text
Low-copy false-free sets: 27
Best low-copy feature set: prev1_low_eq_dominant_low + run_len_bucket + pos8
Best low-copy training correct/false slots: 2/0
Low-copy promotion candidates: 1
Low-copy promoted rows: 1/1
Low-copy added/exact/false bytes: 1/1/0
Total clean bytes after low-copy: 9440
Remaining unresolved bytes: 8006
```

La promotion propre est:

```text
row 6 / frontier 50 / offset 2 -> 6d
```

Les checks residuels apres low-copy bornent le nouvel etat:

```text
output/tex_micro_mixed_value_payload_sequence_low_copy_generalization/index.html
output/tex_micro_mixed_value_payload_sequence_low_copy_second/index.html
output/tex_micro_mixed_value_payload_sequence_low_copy_low_split/index.html
output/tex_micro_mixed_value_payload_sequence_low_copy_corpus_expansion/index.html
output/tex_micro_mixed_value_payload_sequence_low_copy_adjacent/index.html
```

Etat courant:

```text
Post-low-copy replayable unknown slots: 0
Post-low-copy target-known slots: 20
Post-low-copy blocked prerequisite slots: 2
Second low-copy false-free sets: 0
Residual low-split false-free sets: 0
Residual low-split promotion-candidate bytes: 0
Residual corpus false-free rule sets: 0
Residual corpus promotion-candidate bytes: 0
Residual adjacent-known candidate/false/conflict slots: 0/0/0
```

Conclusion: il ne reste plus de slot sequence replayable dans cette piste; les
2 derniers slots sequence sont bloques par des prerequis entierement inconnus.

Une passe role-transform sur les prerequis bloques teste ensuite les memes
prerequis comme roles `first/second` avant une cible a +2/+1, avec validation
leave-one-fixture-out sur les fixtures attendues:

```text
output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform/index.html
output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform/slots.csv
output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform/rules.csv
```

Etat courant:

```text
Blocked sequence slots: 2
Unknown prerequisite slots: 4
Training role entries: 34910
False-free full-byte rule sets: 0
Partial high slots: 2
Partial low slots: 2
Combined nibble candidate slots: 0
Promotion candidate bytes: 0
Best partial high: target_pos4 + target_pos32 + target_low + rule_type -> 2/0
Best partial low: pre_pos16 + pre_pos32 + target_low + opcode1 -> 2/0
```

Conclusion: les roles donnent seulement des nibbles partiels (`5` pour la
paire `5a`, `b` pour la paire `5b`). Les supports hors fixture cible restent
des bytes complets differents (`56` et `6b`), donc aucune promotion full-byte
n'est sure. Ces prerequis restent en attente d'un producteur non-oracle.

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
Gates: 252/252
```
