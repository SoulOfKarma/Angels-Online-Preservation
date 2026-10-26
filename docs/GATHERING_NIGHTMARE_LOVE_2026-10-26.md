# Gathering, Nightmare Cave and Love Broadcasting

## Producer orders

The original Samara Woods HardOak tables (material381..383) do contain the
correct Lv131 order items15931..15934 and15939..15942. Their combined original
weight is520 out of1,000,000:0.052% per attempt. They were not missing from
the gathering implementation; their very low original rate explains long
sessions without an order.

At the user's request, `gathering_rewards.py` now makes the combined order
probability **10% per gathering attempt**. It only adjusts resources whose
original pool already contains an order from `order.xml` (`訂單原型`, not
the order record's own ID). It preserves the resource's eligible order IDs
and all relative weights within the order and ordinary/rare/empty pools.
There is one outcome per attempt; an order replaces its normal output.
Battlefield materials without orders keep their original pools. No event
resource is assigned an unrelated producer order.

For reproducibility, the integer weights are scaled by the two original pool
totals and reduced by their GCD. Tests check the exact10% ratio across every
original order-bearing material and actually gather every eligible Samara
HardOak order into a temporary character's persisted inventory.

## Resource exhaustion and replenishment

`gathering_nodes.py` uses the existing gathering counter and original
`開採上限`/`重置時間`. On the last attempt, the object disappears with S2C0007.
At its original reset time it returns with the original S2C000E body and
S2C000F name. World players share depletion; private houses and instance runs
remain separated. Viewers are resolved again when replenishment happens,
so leaving or disconnecting the player who harvested it does not prevent
the node from returning for the remaining viewers.

Login and map loading filter exhausted objects before sending spawns. A
late scene load cannot cancel replenishment or erase fresh extraction
progress. A full backpack rolls back the final attempt without hiding the
resource. Scene filtering inspects existing depletion counters rather than
rescanning every resource for each object packet.

## Love Broadcasting

The old implementation selected the Public chat channel2. The native client
has a separate love presentation:

- S2C0128 channel15 invokes5F3B40 ->6344A0 with style2.
- Renderer6345C0 selects native frame89 for that style; ordinary Super BC
  uses style0/frame85.
- The original literal `\n` separator is retained for its two text lines.
  The renderer also appends those lines to chat itself.
- The portrait selector comes from the sender's actual appearance. Character
  lookup and item consumption remain atomic; duplicate confirmations do not
  consume twice.

## Nightmare Cave

Breeze Woods Exploration Head had npc_type33, which selected the wrong service
dialogue. It is now1920. Breeze/Iron placement is aligned with their original
MPC NPC records. All four heads and Exploring Members use exact NPC roots
instead of the generic dialogue inferred from a shared portrait.

Original sources: `map003/026/029/038.mpc` root6000, the four field MPC roots6019,
`map061.mpc`, `dialogos_mapa.json`, `eventos.json`, `npc.xml` and `monster.xml`.

- The original permit is2852, Ancient Crypt Passport, bought for50,000 gold.
  The client condition rejects levels below40. Permit delivery and gold are
  committed together; insufficient gold, duplicate claims, a full bag or a
  failed database write do not create a free permit or lose the fee.
- Exploring Members in stages8/9/25/28 require that permit, retain it and
  enter stage61/tag1. South of Mirror Lake preserves its additional quest
  option, so the entrance is not always the first menu option.
  The map transition is deferred until C2S000B/1 finishes warning6022;
  the dialogue closes before the map-change packet. Cancelling, replacing
  the dialogue, moving away, dying or losing the permit cancels admission.
  Repeated completion packets cannot travel twice. This follow-up passed40
  tests covering the cave and NPC mission dialogue flows.
- `nightmare_cave.json` is generated from original map061 generators:40
  passive Cave Slarm and four spirits. Inspector Samir and Inspector Labram
  are restored from the original NPC placements at71,15 and77,10.
- Spirit generator records store their dialogue roots at+60:60101/60201/
  60301/60401. Each stone is consumed atomically before its boss is generated.
  Existing living-boss checks remain in effect.
- The original `TRAS_CREARSE(10)` events now execute for generated cave
  monsters, creating their attendants. This particular client specifies4
  Hook Attendants,2 initial Soul Attendants,7 mixed Tribe attendants and2
  Gebuer Tanks. The Tribe group comprises3 Soldiers,2 Priests and2 Axe Guards;
  this differs from the approximate older description of5 Soldiers. Boss HP
  is223,830 in this client's original monster records.
- The inspectors' original Dream Piece equipment previews and selectable
  rewards are active. Native5ED670 reads byte10 as count|0x80 and the trailing
  item/quantity pairs. `message.lua` confirms C2S000B values20..25 for reward
  selection. Original actions12/47/48 supply the previews, choices and costs;
  one chosen item and the required3040 pieces are exchanged in one transaction.
- The exit tornado at6,5 executes event1. Its original faction conditions
  return Aurora/Beasts/Steel/Shadow to8/9/28/25, respectively, at tag9.

## Remaining recipe data limitation

The earlier screenshot matches recipe2335, required Weapon skill165: ten
Magic Wing Swords18975, not a basic skill200 recipe. It points to drop13971,
whose client preview lists36484 and36489. Their localized ENG XML still has
Japanese names. The current IGG `serv_drop.xml` lacks13971, and the Taiwan
client's available `SERV_DROP.XML` also lacks it. Its result weights have not
been invented. This specific recipe remains rejected before consuming any
materials; supported skill191/195 recipes continue to use their original
available product tables. No client executable or client archive was edited.

## Validation and loading

Tests use temporary databases, not live characters. They exercise the actual
packet router, permit menus, all four field entries and faction exits,
stone/boss creation, native reward selection, rollbacks, order pools and
resource visibility across players and instance runs. The required core
`py_compile` checks and `git diff --check` also pass.

Final regression: **239 passed**, with one existing asyncio deprecation warning,
in35.43s. The additional living-boss replay check also passed.

These changes must be loaded by the server process. No running client or
server was closed or restarted, and no live account data was edited.
