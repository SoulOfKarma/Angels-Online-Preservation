# GvG, scene persistence and production corrections — 2026-10-25

## Combat

The supplied log throws at `int('gvg_field')`. This named HP bonus was being
treated as a numeric spell ID both by the attack-speed calculator and by
buff-priority replacement. Native spell-icon restoration and pet-proc scans
now also distinguish named bonuses from numeric spell IDs.

GvG updates send changed score/player-count fields instead of reinitializing
the battlefield window and PvP/team flags every second. Scene loading still
sends the complete initialization. Tests exercise the actual C2S0006 router
against an enemy statue: normal attack, Slicing Hit V, Cross Chop V, Shock
Wave V, Magic Bomb V and Deadly Combo V. A deterministic timer test runs all
three Deadly Combo V hits and verifies that idle updates send no reset.

## Social state and Alone

The captured scene sequence contained empty friend/trusted lists belonging
to the captured player. These packets are omitted; C2S0009 completion restores
the current character's SQL contacts, trusted list and open mailbox. Blocking
rules remain stored and enforced in SQL.
Chat rooms retain membership and the last 200 messages addressed to that
member. Games retain their board, turn and cards; restoration replays public
frames and only that player's private deal. Map loading does not count as a
voluntary room/game departure. These connected conversations/games are not
persisted across server restarts.

The scene inventory now includes backpack slots121–154 and hidden game-card
slots156–159. Previously both groups were omitted.

Native party invitation615220 uses17 bytes for the target name followed by
the mode byte. The incoming mode was already retained by the server, but the
two outgoing UI fields were hardcoded to Share. Invitation602D80 reads the
mode at full packet+23; group-list506FC0 copies body+4. Both now carry the
actual mode, including after leader promotion.
Retrying Alone after a rejected Share invitation also replaces the stale
mode of the remaining one-person group.

## Production and merchants

The resource lookup now includes Lyceum's separate template. In particular,
entity104 is its original weapon-processing furnace at207,52, not an unknown
NPC. Native object events with action18 now execute `fabricar`.

Native606950 opens WND_MAKE with S2C004B and a one-byte category:
1=Armor/skill27,2=Sewing/28,3=Technics/29,5=Cooking/31,6=Weapon/26.
Stations are matched to the original MPC object events. This covers Lyceum,
Aurora City, Dark City, Breeze Woods, Iron Castle and Palm Base; the house
retains its owner/cleanliness/level rules. C2S0036 validates the nearby station,
skills, known recipe, materials and capacity; the completion commits material
consumption and product delivery atomically. Leaving the station or switching
characters cancels completion. C2S0037 still cancels the pending job.

Another missing field was the recipe bitmap: native5E9C90 copies2048 bytes
from full character packet+1877, while the captured bitmap was entirely zero.
Learned blueprint recipes now persist in `recetas`; using a blueprint consumes
one item only after the transaction succeeds. Native601B50 enables a recipe
through S2C001D attribute11 `(recipe_id,1)`; constructor5FBDD0 registers that
handler at17592. Receiver5F0EF0 uses the extended table at17416, so the index
is `(17592-17416)/16=11`. The previous index93 incorrectly used the separate
simple-attribute table base16104 and only the scene bitmap took effect.
Station opening also refreshes known recipes for players
already online. Basic recipes without a blueprint item are derived from the
original make.xml skill/level requirements; this automatic-unlock policy is
a server reconstruction, not a captured official unlock sequence. Blueprint
references come from the original item.xml through item9.xml. Equipment
quality rolls now use the original serv_drop.xml product IDs, quantities and
weights. Recipes whose original product tables are absent remain blocked
without consumption; available tables no longer hit the blanket rejection.

Pure merchant trees now use the MPC root for the exact NPC. This preserves
native level-band submenus and shop IDs while avoiding generic portrait/option
fallbacks that could select another merchant's menu. Quest-bearing trees and
other service actions retain their existing handling. Party Angel's three
Renewal Lv200 boxes were verified through the real item-use router to deliver
all four/five/four documented pieces and persist the result.

Party Angel, Gear Clerk and Fashionable service clones no longer spawn outside
Lyceum. Original city/Palm merchants and processing apparatus remain.

The city plan sellers used portrait numbers as sprites; Breeze additionally
used141–145 as NPC types. They now use npc.xml sprites and Breeze types1854–1858.
The following sellers also moved to nearby walkable tiles clear of furnaces:

| Map | Seller | Before | After |
| --- | --- | --- | --- |
| Aurora City | W. Plan Seller |291,93|292,90|
| Dark City | W. Plan Seller |315,140|315,137|
| Dark City | A. Recipe Seller |324,133|321,133|
| Breeze Woods | W. Plan Seller |228,189|227,192|
| Breeze Woods | A. Recipe Seller |239,180|236,179|
| Iron Castle | A. Recipe Seller |242,141|239,142|

## Verification and rollout

Tests use temporary databases and simulated sessions/timers. They cover all
five production categories in six public maps, house production, blueprint
rollback/persistence, native merchant selection, Renewal boxes, social map
transitions, private game hands, Alone and timed statue attacks. Core/runtime
compilation passed. The integrated suite finished with **414 passed**,29
asyncio deprecation warnings, in143.55s. The final invitation-retry adjustment
was additionally checked with both party/social suites (**30 passed**).

REA's decompiler timed out; protocol offsets above were checked against the
existing Angel_unpacked.c and targeted Capstone disassembly of G:/Angel.exe.
REA was closed normally. No executable patch, live account mutation, process
restart, commit or push was performed. A new server process is needed to load
the changes; visual interaction still needs a live-client check.
