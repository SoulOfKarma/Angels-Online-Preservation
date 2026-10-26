# Angels Online — local server

**\*English** · [Español](README.es.md)\*

Reverse-engineered network protocol for **Angels Online** (IGG, shut down in
February 2026, client 8.5.1.0) and a server that speaks it, built from the client files and
from traffic captures.

This is not a complete emulator. It is the **documented protocol** plus a
server that goes as far as it goes: you can create a character, run the
tutorial, pick a class, fight monsters, level up, and buy and sell in shops.
What is missing is listed below, without sugarcoating.

Every protocol claim in here has a measurement behind it. Where something is
a guess, it says so.

---

Social services, native Album, Angel Elementary and League War are connected.
[Implemented behavior, GM commands, original reward evidence and remaining limits](docs/SOCIAL_ALBUM_QUIZ_GVG_2026-10-25.md).
[GvG, social map persistence, Alone and production corrections](docs/GVG_SOCIAL_PRODUCTION_FIXES_2026-10-25.md).
[Immediate recipe learning, /recipes, producer orders and Wolay exit](docs/PRODUCTION_FRIENDS_WOLAY_2026-10-25.md).
[Gathering order rate, resource replenishment, Nightmare Cave and Love Broadcasting](docs/GATHERING_NIGHTMARE_LOVE_2026-10-26.md).

Arena/Holy: GM registration/join/begin controls, free-for-all Arena by default
(optional brackets), orange/blue Holy teams, original mines and exits,
hidden spectators, team chat and original achievement rules are connected.
[Runtime fixes, timed passes and configurable custom EXP](docs/HOLY_RUNTIME_Y_PASES_2026-10-22.md).
[Measured proxy dialogues and real-save admission fixes](docs/DIALOGOS_COMPETICIONES_PROXY_2026-10-22.md):
semantic inventory checks, confirmation before charging, and4M/8M fees.
[Testing guide and official reward-data limits](docs/ARENA_HOLY_LOGROS_Y_PRUEBAS_2026-10-22.md).

Outpost 47/48 now has permanent faction PvP and original portals. Wolay,
name parameters, map-loading races and summon PvP/disconnect cleanup are covered
in the [runtime notes and verification](docs/OUTPOST_Y_RUNTIME_2026-10-22.md).

## Actual state

Olympus: Olly/Ozzy, exchanges, maps 217/332 with per-floor waves, and Omos results
connected to rankings. Item Mall: cleaned catalog excluding event/bound bags, 5X stones,
and placeholder question-mark items (9407..9416); class eggs (80489..80495) sorted first;
purchases/gifts and Store Cabinet with 1,000,000 initial AG. Star Blessing has native state,
upgrades, 27 recipes, corrected S2C 0x017F length and matrix/draw/storage mapping, and atomic Star Key draws.
Auto Divine fills outcomes one card at a time; native Coin costs, free IV/V draws,
Stardust and screenshot Bingo rewards are connected. Latest verified 2025 Mall
root bags populate On Sale/Fashion/Bubble; Top Sale uses local purchase history.
City scrolls, persistent Mark/Maple destinations and party travel books are handled atomically.
Producer Classes & Crafting: repaired full gathering and crafting pipeline for Weaponsmith, Armorsmith, Tailor, Chef, and Craft (Technician).
Gathering nodes (Mining/Dig, Woodcutting/Lumber, Fishing, Herb/Foraging Collect) enforce skill presence, skill level requirements (native notice 356), and proper tools or robot mounts.
Robot rides (機甲) enable universal gathering with Drive (skill 25) providing gathering speed reduction bonuses and Mechanism (skill 24) enhancing vehicle attributes; successful extraction awards Skill EXP to the gathering skill as well as Drive and Mechanism when mounted.
Native manufacturing (`0x0036`/`0x0037`) uses the original stations in Lyceum, the four cities, Palm Base and houses; known recipes and blueprint learning persist, with atomic material consumption and product delivery.
Skill Angel supports unrestricted skill exchanges (`0x002F`, container 10) for producer classes, with corrected `calcular_class_id` preserving craft professions even when equipping weapons or daggers.
Choosing any producer class grants the basic robot ride `Freshman Cask` (19814) in the mount slot, and confirming tutorial completion warps directly to Angel Lyceum.
Production & Material Processing Zones: restored sprites, official dialogues, recipe/material shops, and exchange NPCs (`Party Angel`, `Gear Clerk`, `Fashionable`) across Angel Lyceum, the four faction cities (Aurora City, Dark City, Breeze Woods, Iron Castle), and Palm Base, including `Ironsmith`, `Salesmen`, `Directors`, `Clerks`, and `Plan Sellers`.
Party Angel exchanges now support `Renewal-Lv 200 Equipment Voucher` (72058) and opening `Renewal-Lv200 Light Armor`, `Heavy Armor`, and `Gown` boxes (72059..72061).
League War redeem shop now includes all Battlefield Badges from Lv 13 to Lv 28 (48017..48024, 79352..79359).
Album persistence (`cuentas.py`) preserves `_entries` cell lists across character login and save cycles.
Daily Events: two distinct games per day in a configurable local weekly rotation (42 bracket rows);
atomic simultaneous opening of all 4 level tiers, automatic character level bracket routing on entry,
periodic EXP (scaled with level up to ~2M) and Skill EXP (~100) delivered via standard system notices without false combat float numbers,
faction-specific platform spawns and returns in Swindle World (Aurora 97,158; Beasts 95,51; Steel 305,52; Shadow 303,155) with dedicated exit portals,
top rolling banner announcements (/notice style) for registration start, battle start, and event completion, visible and walkable
exit warps back to Angel Lyceum (radius 2, with Training City exit under the clover archway at 28,25),
and preservation of the original chest return mechanic upon opening.
Use /daily start and /daily enter for GM checks. Original server schedules and draw odds remain unavailable.
Angel Lyceum: restored missing NPCs Astral Angel (Star Key exchange 393), Party Angel (renewal gifts & exchange 245),
Chat Bubble Exchange (groups 559, 570), Fashionable (voucher recipes), and Reissue Angel.
Party Angel applies the original 12-hour Archangel's Secret; Compensation Angel is removed.
[Sources, tests and limits](docs/MALL_STAR_FURNITURE_DAILY_2026-10-24.md).

Supreme Power now enables the client's PLV label without changing the real
level or adding skill slots. Blessing Angel and BattlefieldAngel's lobby
dialogue are restored. Arena/Holy Battlefield now have persistent rounds,
registration, isolated PvP and separate GM commands; Holy includes crystal
capture. XML schedules use server local time. Holy buildings now have
persisted construction and gate collision rules.
This is unfinished work: production scheduling is disabled and GM rounds are
GM tests with normal gold/stone admission until the official reward pipeline is completed. Olympus weekly prizes and Census
transfers remain pending. See [commands and limits](docs/COMPETICIONES_GM_2026-10-22.md).
See [implementation scope and original competition rules](docs/PLV_Y_COMPETICIONES_2026-10-22.md).

Crashing Hillock's totem is now at `(92,174)`, validated in game by the user.
The unsuccessful shadow experiment is rolled back without changing war rules.
See [position and rollback notes](docs/TOTEM_SOMBRA_2026-10-21.md).

Buff resource and Peril Chasm collision fixes (Oct 21): maximum HP/MP buffs
no longer refill current resources; conditional Meditate buffs select their
XML effects. Blocked monster spawns no longer disable map collisions.
See [evidence, tests and remaining limits](docs/BUFFS_MP_Y_COLISIONES_2026-10-21.md).

Aliua's quest preserves the existing skill slots, including slots 7–9,
and never grants a tenth slot. See the [reward compatibility notes](docs/ALIUA_SIN_RANURAS_EXTRA_2026-10-21.md).

Oct 21 pet release: [scope, tests and remaining limitations](docs/ENTREGA_PETS_2026-10-21.md).

Pet progression (Oct 21): fixed fusion blocked by initial bonus ranges,
general-star desynchronization and the first enhancement feed missing its
increment. Official enhancement coefficients remain unverified; existing
pets are not automatically compensated.
See [audit, fixes and tests](docs/PETS_ESTRELLAS_AUDITORIA_2026-10-21.md).
Pet combos now send one skill effect followed by their damage ticks,
without replaying the cast per hit. Player combat is unchanged by this fix.
Equip Pet slot 558 now accepts 5.0+ star pets and applies/removes their green
stat contribution. See [equipment and level-growth notes](docs/PET_EQUIP_Y_CRECIMIENTO_2026-10-21.md)
for tests and the provenance/limits of the implemented rules.

Lyceum services (Oct 21): Astrologer, Login Rewarder and Green Angel,
including persistent fees/quotas, exchanges and level-21+ Straw drops.
See the [NPC service notes](docs/LYCEUM_NPC_SERVICES_2026-10-21.md)
for evidence, tests and explicitly provisional drop/draw probabilities.
Green Angel includes the mount catalog (group 401); Login Rewarder is at
`(141,106)`. Straw drops now read missing monster levels from `monster.xml`.

Farm interaction range and soil/crop refresh have been corrected;
experimental action animations remain disabled pending client validation.
See the [Farm investigation](docs/FARM_INTERACCIONES_2026-10-21.md).
This release also includes the previously pending EXP/honor vouchers,
permanent-stat items and `app` startup alias changes;
see [release scope and validation](docs/ENTREGA_2026-10-21.md).

**Works**

- Login, character creation, selection and deletion, saved to disk
- Entering the world, movement, changing maps, and floor teleport zones
- Angel Raphael's tutorial: picking a class, getting the gear, the transfer
- Inventory with **quantities**: consumables stack, and equipping, unequipping
  and moving between slots all report back per slot, the way the real server
  does
- **IGG Card Book**: all 459 collectible cards and 106 sets are read from the
  last IGG client's own tables. Registering a genuine card consumes exactly
  one unit, updates the native Card List immediately, and persists ownership
  across reconnects. Non-card items and duplicate registrations are rejected
  without consuming anything
- **Card-set rewards**: both "all rewards" and "choose one" sets use the
  client's native exchange request. Completion and one-time redemption are
  validated server-side; rewards and redemption state are committed atomically,
  so a full bag or a failed save cannot grant partial or duplicate rewards
- The extended inventory block is synchronized across **Fashion, Card and
  Furniture slots (167..556)**. Moving an item from a high slot such as Card
  slot 280 back to the normal bag now clears the source with the native
  `0x001B` delta instead of leaving a duplicate instance that crashes the client
- Shops: buying **several items and several units in one go**, selling,
  splitting a stack and destroying one. Buy and sell prices come from
  `item.xml`, and the sale total matches the captured one to the gold
- Using consumables: potions and food restore HP and MP and spend one unit
- Stats computed from `item.xml` (gear actually adds up), including carry
  weight
- Combat: hitting and being hit, damage numbers, criticals, dual wield,
  attack effects, dying and reviving, loot, experience and skill experience
- Monsters: per-monster attack cadence, chasing, wandering, respawn, and
  bleed and stun effects
- **Telling monsters from NPCs does not rely on the `klass` byte alone.**
  The live server sends some monsters with the NPC marker 199 -- 88 spawns
  across eight maps, which ended up as friendly NPCs with no AI. The client's
  own data settles it: `npc.xml` runs from 1500 to 24893 and `monster.xml`
  from 1 to 23860, and they share **no id at all**, so above 1500 the answer
  is certain. Below 1500 the `klass` still decides, because `npc.xml` does not
  reach down there and the old Lyceum NPCs use two- and three-digit numbers
  that collide with `monster.xml`
- **255 maps populated from captures**: 42,860+ monsters, 2,350+ NPCs and
  15,059 map objects, 7,671 of them with their resource name resolved. Every
  monster, NPC and resource comes from a capture; none of it is made up
- **Twenty maps do not come from the main server, but from a second one**:
  three whole zones -- **Night City Code**, **Sun Sea Maze** and
  **Cybertronica** -- plus two Training Areas. It is the only exception to
  "everything comes from captures of one server", and it is explained below in
  _The three zones that came from elsewhere_
- **Whole zones are closed**, meaning every tornado in them has been crossed
  and measured: **Heart of Eden**, **Floating** (6 maps), **the desert ring**
  (Crescent Valley, Desert Racetrack, Ghost Village, Troop Outpost, Ancient
  Front, Fantastic Sand City, Nightmare Palace) and **Candyland** (7 maps).
  **Atlantis is complete except for the instances** (including the central city
  of **Palm Base**, populated with its 50 NPCs and 22 verified shops and services),
  and the forest chain
  (Cryptic Moon Swamp to Giant Wooden Stairs, 8 maps) only has two tornados
  left. Plus a good part of Pharaoh, East Orient and the four faction
  territories. The late-game chains added last are closed too: **Arcana**
  (Starglow Path, Academia Woods, Mana Ruins, Coo Village, Ethereal Garden,
  Daydream Library, Reminiscence Cloister), **Goldenia** (Emerald Coast to
  Royal Ruins, 9 maps), **Abyston** (Forsaken Crevasse, Specter Village,
  Crystal Marsh, Crystal Quarry, Shrouded Haven, Peril Chasm) and the deep
  chain from Galaxia Square to Deep Prison
- **572 portals**, 551 of them active, almost all measured in both directions: the tornado's tile
  comes from the capture, and so does the tile the real server drops you on.
  Most of them were crossed **twice in each direction**, which is how we found
  out that some portals do not always drop you on the same tile
- **Portals that lead somewhere else on the same map** work: **29 of them**,
  across seven maps. Lost Trail alone has twelve -- six pairs that move you
  from one end of the map to the other --, Horizon Archives has five and
  Branch Way has two pairs. They do **not**
  reload the map -- measured over 1,401 seconds without a single `0x000C`.
  The server answers `0x0016`, a `0x0012` of seven zeros and a `0x0003` that
  just moves the character
- **Portals can carry their own menu.** Teddy Amusement's hub asks "Move to
  which area?" and sends you to one of two spots on the same map. Each portal
  brings its own message id and its own option-to-tile table, so a new one is
  data, not code
- **15 more portals are recorded but switched off**: **fourteen instance
  entrances**, the one Lost Cove portal that was never measured, and the Niro
  River tornado to Clink Harbor -- that map exists in `stage.xml` but the
  live server has no content for it. The entrances were found by crossing
  the maps and cross-checking against the client's own `jumpmap.xml`, which
  labels them with **two different names**, `Instance Entry Point` and
  `Instance Entrance`
- **Angels GO!, the Superwing teleport**, works: `0x0151` carries the entry id
  from the client's own `jumpmap.xml`, a Superwing is spent, and the answer
  splits in two, both measured -- a `0x0003` when the destination is on the
  map you are already on, a `0x0007` plus `0x000C` when it is another map.
  The table has **355 destinations** and **224 of them are live**, the ones
  that land on a populated map; the rest are refused without spending the
  item. A character who does not belong to one of the four factions cannot
  use a Superwing at all -- measured on a level 12 still in "Heaven"
- The four faction cities with their arrival tile, all four measured: Aurora
  City, Breeze Woods, Iron Castle and Dark City. Picking a faction leaves you
  next to that city's Angel, three or four tiles away, in all four
- **The full leave-the-Lyceum flow**: the Angels' Tutor, choosing a faction at
  the Graduation Palace, travelling to your city, registering with its Angel
  and being sent back to the Lyceum. It works in **all four cities**, each
  with its own text, its own registration quest and its own follow-ups
- Portals between the Lyceum and both playgrounds, with their menus
- Cupid sets your revival point where you are standing
- Per-weapon attack animation and rhythm, measured: spear, staff, sword,
  dagger and dual wielding each send their own pair of values
- Skill cooldowns come from each skill's own data, separate from the basic
  attack rhythm
- Mages can swap a magic branch: the spells of the new branch are granted
  and the old branch's are dropped
- **Magic and skill system**: implemented combat and magic branches (Life,
  Wraith, Chaos, Earth, Curse, Meditate, Hit, Staff Hit, etc.) with initial
  spells, MP costs, and quick-bar assignments
- **Spell damage formula & scaling**: base damage computed from Spell Attack
  (SA) and spell multiplier minus target's effective Spell Defense (SD), plus
  elemental affinity modifiers (Fire, Ice, Thunder, Corrosion) and spell damage %
- **Cast times and reductions**: dynamic cast times read from `content.db`,
  supporting flat cast time reductions from active self-buffs (`First Path`,
  `Third Spirit`, `Limit Breaker`, `Shadow Meld`, `Killer Intent`) and the
  **50% cast reduction** from passive `Curse Spell` (ID 5)
- **Distinct casting animations**: magic spells play proper hand-casting
  animations and ground circle glyphs (`0x0011` byte 20 = 1) without triggering
  phantom dual-wield melee strikes (`0x000A`)
- **Level up visual banners (`0x0020`)**: cherub and trumpet animations (red
  banner for character level up, blue banner for skill level up)
- **Skill EXP progression**: leveling up skill ranks (up to level 300) through
  both physical and magical combat, distributing experience to active and class
  passive skills based on damage dealt
- **Dynamic Job / Class ID calculation**: automatic character Job ID
  determination based on currently equipped skill trees
- **Skill Scrolls & Books**: reading and learning new skills from scrolls
  found in `content.db`, fully persisting learned skills across sessions and
  map changes without losing them or reverting to `?`
- **Wraith Summoning System**: full implementation of minion invocations across
  all 11 families and 55 skills (Death's Head / Skeleton, Death Mummy, Death Leech,
  Azrael, Soul Eater / Muncher, Demon I-V, Demon Summon I-V, Ghostly Swordsman,
  Putridox, Minotaur, and Earth Titan / Golem). Features ground portal/coffer
  summon animations at target tile (`tx, ty`), minion entity spawning (`0x0008`),
  dedicated minion HP bar (`0x0013`), player-minion bidirectional binding links
  (`0x3c` and `0x3d`), autonomous combat AI, cross-map persistence (`0x000D`),
  and authentic attack cadence/speed calibration
- **Ground & Self Area of Effect (AoE)**: execution of ground-targeted and
  self-centered AoE spells (Strong Acid Rain, Hell Flame, Frozen Trap, Fire Trap,
  Thunder Scope, etc.) on any valid tile without requiring an enemy target,
  with ground glyph and impact visuals (`0x0011`)
- **Ring of Angel Wings**: teleportation back to the Cupid revival checkpoint
- **Expanded NPC Dialogues & Official Shops**: dynamic dialogue, quest interactions,
  and verified vendor shops across faction cities, regional hubs, and dungeons:
  - **Palm Base (Stage 88 - Atlantis)**: all 50 NPCs populated with exact dialogues,
    sprites, and 22 verified shops/services (level 80-90 skill trainers/deputies,
    bowset & weapon sellers, high-level smith/master recipes, stuffshops, craft clerks,
    native equipment repair, warehouse bankclerks, and pet services)
  - **Lava Cave (Stage 69) & Flaming Door (Stage 70)**: level 60-70 smith and master
    crafting recipes (Rock Smith & Rock Master), advanced weapon and bow researchers,
    and magic trainers (Earth Life Mage & ChaosWraith Mage)
  - **Eleven cities verified byte-for-byte** against what the real server sends, with their
    vendors, bank, repair and shops: Whitefang Village, Coo Village, Rainbow Town, Twinkle
    Town, Specter Village, Teddy Amusement, Galaxia Square, Desolate Sea, Chilly Village
    (Celestia region) and Busy Market (Warring Realm region)
  - **Floral Alley (Stage 398, Sun Sea Maze region)**: the only one populated **without a
    capture**. The dialogue comes from `msg.xml` (block 516188-516210) and the shops from
    `shop.xml`, where every city adds a pair and the odd id is sword skills while the even one
    is spells: `Researcher (C)` opens shop 221 (Edge Guard I) and `Researcher (S)` opens 222
    (Astro Impact I), both level 310
  - **Clank Oasis (Stage 407, Cybertronica) and Commercial Street (Stage 419, Night City
    Code)**: also without a capture, from `msg.xml` blocks 516648-516657 and 517063-517068.
    They key off the **stage**, because `Spell Analyst` and `Technique Analyst` appear in both
    maps with different shops: 223/224 in Clank Oasis and 225/226 in Commercial Street
  - **Faction Hubs & Outposts**: Cherry Village, Memory Cave, Mysterious Garden,
- **Past the Time Spirit & Weekly Quest 976**:
  - The Rainbow Town NPC uses its official sprite (`40542`), portrait (`1342`), south-facing direction, and level 250 gate. Its menu opens Chaos-Dinosaur Arena (Stage 413), Chaos-End Time (Stage 414), Time Crystal exchange shop 659, or leaves the dialogue.
  - *Nature is Crying for Help* awards the official level-scaled EXP (36M below level 90, 48M at levels 90-94, and 72M from level 95), one Weekly Quest Mark (`12611`), and 50 Honor Credits. It neither charges nor awards gold, eliminating the erroneous `Pay 29480` message.
- **Comprehensive Pet System (85-90% Complete)**:
  - **Summoning & Hotkey Management**: Right-click bag summoning, hotkey bar (F1-F12) activation, and multi-pet management. Switching pets cleanly despawns the previous entity without leaving ghost duplicates (`0x000E`, `0x001B`, `0x015E`).
  - **Evolution & Growth Stages**: Automatic form progression from Egg to Junior Pet at level 15, and certificate-driven evolutions (Medium Blood Certificate at Lvl 35, Advanced Blood Certificate at Lvl 55) with instant model/sprite refresh.
  - **Feeding & Satiation**: Consuming `Pet Feed` adds 500 satiation (up to 1,000 max). Reaching >100 Satiation Degree triggers the official `Pet's Satiation` buff (ID 3796) above the pet portrait.
  - **Pet Star System (`pet_star.xml`)**: Full integration of all 80 star levels (0.1 to 8.0 stars). Enhancing pets with `Improved Pet Feed` or `Star-up Cards` grants official stat bonuses across all attributes.
  - **Complete 231-Byte Inventory Tooltips**: Displays individual base and green star bonuses (`Attack 606 (444 + 162) Star Level: 0.4`), overall `Star Level: 0.4`, and `has been intensified ( N ) times`.
  - **Pet Status Window (`0x0065`)**: Displays green highlighted effective combat stats, base values, active pet skill slots, elemental resistances, and star ratings.
  - **Pet AI & Commands (`0x003E` / `0x001D`)**: Full support for Quiet (0), Follow (1), and Attack (2) companion modes.
  - **Captured Monsters & Poke Eggs**: capture eligibility and base probability come from `catch.xml`; egg variants modify the chance instead of forcing 100% success. A failed attempt consumes the egg and locks that living spawn until it is killed and respawns. Every attempt shows Icy Trap; success additionally plays the absorption toward the player, reports success, stuns, and despawns the captured monster after a delay. Fire Trap is never used.
  - **Faithful Captured Pet Identity**: captured species, names, combat archetypes, skill families, and Common/Good/Rare/Awesome/Super quality are preserved through growth and evolution without inventing unrelated forms or inflating star levels.
  - **Shared Companion Combat Visuals**: nearby players receive attacks, skills, buffs, healing, and HP changes from pets, summons, and mercenaries. Magical and physical pet skills use their matching visual packet path, including Dawn Shield without the unrelated Wraith Hell Flame AoE.
- **SP System (Holy Power / SP Lamps)**:
  - SP point generation from combat actions up to maximum capacity (2000 SP / 4 lamps). Full session persistence across logouts.
  - Instant SP skill execution (e.g., `Earth Blessing V`, `Shark Shift V`, `Angel Protection`) with tick timers, HP/MP recovery, and stat enhancements.
- **Buffs, HoT & DoT Tick Engine**:
  - Timed buff management for self-buffs, regeneration ticks (Earth Blessing HP/MP HoT), potion effects, and long-duration utility cards.
- **High-Tier Combat & Skill Progression**:
  - **Multi-Hit Combos & Continuous Barrages**: full support for chained skills and continuous attacks (formulas 36, 40, and 42, e.g., *Rapidfire*, *Steel Rain*, *Victory Sword*, *Quake Spear*, *Strangle Strike*, *Windbreaker Arrow*). The player character model performs the casting/shooting animation strictly **once** at invocation, while subsequent combo hits land with smooth timing intervals.
  - **Faithful AoE Barrage & Ricochet Distribution**: AoE barrages (*Steel Rain*, *Sword of Kings*, *Quake Spear*, *Flaming Blade Rain*) distribute their N combo strikes randomly among alive enemies in the area (focusing all strikes if a single target is present). Windbreaker Arrow executes an initial ground tornado AoE strike followed by 5 to 10 sequential ricochets against nearby enemies.
  - **Physical Skill Scaling & R.Atk Baseline**: physical skills scale faithfully from main-hand attack power (`R.Atk`) and Stance Power (`PESO_STANCE = 2.0`) against target defense. Combos apply a calibrated +0.2x boost (`1.2x` per hit) and single-hit strikes use `1.35x`, with Rapidfire applying its official 50% damage penalty against boss monsters.
  - **High-Tier Skill Delegation**: launcher skills for archers and long-range classes (formulas 63 and 7, e.g., *TNT Arrow*, *Aparctias Shot*, *Toma Tornado*, *Windbreaker Arrow*) resolve their combat sub-spells to inherit genuine Stance Power, AoE explosion radii (5-6 tiles), and secondary debuffs (knockback, silence, elemental DoT, blind).
  - **Summon & Totem Secondary Effects**: summons and totems trigger their automated auras and DoTs (e.g. *Black Thorn Totem* corrosive DoT and slow), enforcing official non-coexistence rules with *Guardian Star (Starchaos)*.
  - **Account & Character Management**: safe character deletion via raw `0x0004` response preventing client crashes, alongside transparent SQLite `cuentas.db` migration from legacy `cuentas.json`.
- **Bound Equipment & Enchanted Fashion with Residual Times = 0**: ownership verified by persistent `char_id` (offset 53 of packet `0x001B` / `sub_58B640` in `Angel.exe`). If the player is the registered owner, the item can be equipped freely even when 0 residual times remain.
- **NPC Sale of Bound S/Fine Equipment**: the local client keeps reward equipment non-tradable between players while adding an NPC buyback price equal to half its list price, so high-tier bound weapons and armor no longer accumulate permanently.
- **Weapon Switching (Slots 11 & 12)**: quick swapping between primary and alternate weapon sets with dynamic stat and bonus recalculations.
- **Equipment Enhancement & Piercing System (Pestles, Enhanced Pestles, Piercing Hammers)**:
  - Full support for enhancing and socketing level 410+ endgame equipment using tier 40 tools (40-Star Lucky Enhanced Pestle, 40-Star Lucky Piercing Hammer, and standard pestles).
  - Gem inlaying into sockets, Green Hammer rerolling (additional attribute rolls parsed from `adv.xml`), genuine success rates, and level penalties on failure.
- **Personal Bank & Self Storage System**:
  - Full support for depositing (`0x0038`) and withdrawing (`0x0039`) gold to/from the bank via the client's native *Sum* input dialog, with persistent `banco_oro` in SQLite `cuentas.db` and realtime two-way sync.
  - Proper right-click handling: container 16 (`usebankitem`) withdraws from bank slot to bag, and container 17 (`usecharitem`) deposits from bag slot into bank without slot misalignment or item collisions.
  - Seamless drag-and-drop between bank and bag (or within bank slots) mapping genuine slot IDs (1..48 in bank, 20..163 in bag).
- **Robust Inventory Packet Sync**: stackable consumables, slot-by-slot delta sync via official `0x001B` without client stream desynchronization.
- **IGG House System & Private Space (Stage 500)**:
  - **Deed Activation & Stage 500 Instancing**: using or purchasing house deeds (10115..10117, 17934..17937) creates and activates private residential instances on Stage 500 (Stage Type 255) with persistent ownership in SQLite (`casas`, `casas_muebles`, `cuentas_casas_servicios`).
  - **Furnish Mode & Free Placement**: toggle furnish mode via `0x0136`/`0x0137` with graceful exit (`0x0138`). Dynamic placement, movement, and retrieval of furniture items (slots 376..496) mapped from `furniture.xml`, calculating decoration score and room capacity.
  - **Independent furniture copies**: inventory and map loads share unique IDs for every registered copy. Saving or retrieving a decoration uses its exact ID, preserving other copies of the same item; old hidden copies reappear after reconnecting. Layout and inventory are saved atomically.
  - **House Bulletin & Guest Access**: house bulletin board (`2625`) outside and inside for entering own house, visiting friends/strangers with password protection (`0x0135`), guestbook greeting, and message logs.
  - **Maid Eilian (`2603`)**: authentic sprite (`40182`) and portrait (`182`) located at `(44, 80)`. Offers house information, daily blessing buffs (2292..2295 for EXP/Combat boosts), party/ball hosting, and service shortcuts without accidental ejection.
  - **Cleanliness & Liquid Soap System**: dynamic cleanliness tracking capped at 1000. Using soap items (Liquid Soap 10118) raises cleanliness; maintaining $\ge 500$ grants a scaling character bonus (+1% up to +10% EXP multiplier).
  - **Private Rooms & Authentic Layout**:
    - Doorstep portal 701 at `(45, 78)` leading to private utility rooms.
    - **Raise-a-pet Room**: Pet Care Machine (`721`), Safe / House Storage (`723`), Suft's Mailbox (`262501`) at `(37, 25)` for producer orders, and return portal (`702`) back to the main house hall.
    - **Monster Hatching Room**: Monster Incubator Machine (`731`) and return portal (`703`). Clean room layout matching authentic IGG structure.
  - **House Services & Producer Orders**: safe item deposit/withdrawal (`house_services.py`), automated producer material deliveries via Suft's Mailbox (`producer_orders.py`), and Mercenary Token consumption (`10581` -> buff 2254, 8 hours).
  - **Guest Permissions & Portal Flow**: When a visitor enters someone else's house, Portal 701 at the doorstep immediately teleports them back outside without revealing the owner's private room menu. When speaking with Maid Eilian (`2603`), guests are restricted to the official popularity voting dialogue (`7897` with "Vote" `7898` and "I'm leaving" `7899`, or `7922` if they already voted today), hiding all owner blessing and token options.
  - **Outdoor Exhibition Zones & Placement Restrictions**:
    - Outdoor exhibition (`0x0137`) is strictly restricted to designated residential and city spaces: **Angel House Area** (Stage 370), the four faction capitals (**Aurora City** 3, **Dark City** 26, **Breeze Woods** 29, **Iron Castle** 38), and **Palm Base** (88). Placement in unauthorized wilderness, dungeons, or inside buildings/domes (such as the Ocean Scholar dome `(278, 138)` in Palm Base) is blocked.
    - Placement validation enforces designated open grounds: Aurora City is strictly delimited to the central open cobblestone plaza (blocking sidewalks/veredas, cafe tables, and buildings), Dark City includes central monument exclusion, and Iron Castle enforces a minimum 5-tile safety margin from all NPCs so houses never overlap or obstruct NPCs. Requires a full $5 \times 5$ walkable clear area (blocking placement on narrow bridges, stairs, catwalks, near trees, or in tight corridors), a 6-tile safe margin from map borders, at least 7 tiles distance from portals/entrances, and at least 4 tiles from other outdoor houses.
    - Decorating visibility lock: entering furnish mode (`0x0136`) is blocked while the house is currently on display outdoors (`is_open`), and only returns when the house is taken back/not showing (`0x0139`).
  - **Chat Box Notice Routing (`tipo=7`) & Global Notice Fix (`0x000D`)**:
    - House placement restrictions, decoration errors, and password notices are routed with `tipo=7` and `MSG_TEXTO`, directing text cleanly to the bottom chat box and completely eliminating intrusive floating text banners across the middle of the screen.
  - **Faction City Bankers & Voucher Angel**:
    - **Authentic City Bank Greetings**: Restored official welcome dialogues for faction banks: 5232 for Breeze Woods, 5228 for Iron Castle, 5230 for Dark City, and 5225 for Aurora City.
    - **Banker Guide (Option 5030)**: Correctly displays the official storage usage explanation (5034) with warehouse and safe usage instructions, rather than prematurely opening storage.
    - **Breeze Woods Bankers Fix**: Corrected NPC type (`npc_type: 1686`, sprite 40034) for all five Breeze Woods bank clerks.
    - **Universal Voucher Angel Spawns**: Spawned Voucher Angel (`npc_type: 14334`, `sprite: 40041`) near the banks in all four faction cities (Aurora City `[313, 150]`, Dark City `[165, 144]`, Breeze Woods `[313, 142]`, Iron Castle `[141, 136]`), Palm Base (`[154, 76]`), and Angel Lyceum (`[181, 98]`). Lifted the `stage == 41` restriction in `dialogos.py` to allow exchanging 10M and 100M Angelic Vouchers (Shop 159) everywhere.
- **League / Guild System (Ligas)**:
  - **Creation Across All Four Cities**: League Clerks in Aurora, Breeze, Iron, and Dark cities route cleanly to dialogue tree 5776, validating Level 25+, Peerage Rank 3+, and 60,000 gold. Triggers native creation window via `0x001D` action 20.
  - **Immediate Login Sync**: `0x0055` (`paquete_datos_gremio`), `0x0058` (member roster), and `0x0056` (announcement bulletin) delivered immediately upon connection (`0x0002`) without requiring a map transition.
  - **Overhead Name & Crest (`0x0001`)**: Displays official guild logo ID (byte 113) and ASCIIZ league name (byte 114) hovering above player characters.
  - **Guild Warehouse / Vault (`0x0059`)**: Distinct from personal storage (`0x004E`). Enforces granular permissions (`GUILD_PERM_WITHDRAW_ITEM = 1`, `GUILD_PERM_WITHDRAW_MONEY = 2`), atomic SQLite item/gold transfers, and preserves pet/enhancement metadata.
  - **Reputation & Promotion**: Progression thresholds loaded from `update26/setting/level.xml` (0 to 9,375,000 reputation across levels 1 to 10). Material contributions processed via C2S `0x004B` using `guild_contrib.xml`.
  - **Chat Routing**: Automatic routing for league channel 5 (`@`, `/g `, `/guild `, `/l `, `/league `) and party channel 4 (`#`, `/t `, `/team `, `/p `, `/party `).
  - **GM Management**: Dedicated commands `/guildlevel <1..10>` and `/guildrep <amount>`, completely isolated from character level `/level <1..471>`.
- **Guild Farm (Stage 501)**:
  - **Gated Access**: Gated to League Level $\ge 6$ on server side; opened via native UI button (`0x014C`) or `/farm enter`.
  - **Isolated Instances & Persistence**: Isolated per-guild room `(501, 'league', guild_id)`. Entering logs prior stage and tile; exiting through the authentic tornado at `(97, 8)` returns the character to their exact origin.
  - **Plots**: the 70 plots of farmland are sent as `0x015D` entities (dry land sprite 66902) at the exact pixel position of the `farm.mpc` markers. There are no NPCs in the farm: only the land and the exit tornado.
  - **Crop Lifecycle**: plant by using a seed next to an empty plot (or `/plant <crop_id> [plot_id]`); one crop per player at a time. The crop grows through the client's own stages: seeding (66907), sprout (66906), growing (66904), and the `crops.xml` crop sprite once ripe. Watering (C2S `0x014D`), fertilizing (`0x014E`) and harvesting (`0x014F`) follow the official per-crop and daily caps, with secured harvest for the sower.
  - **Rewards** (in-game help, string.xml 3165/3166): watering gives EXP, fertilizing gives Skill EXP, harvesting gives both plus the produce, scaled by the waters and fertilizers the crop received. Amounts are a percentage of what the current level asks for, so they stay useful at high levels.
- **Totem War Infrastructure & Private Territories**:
  - **Territory Ownership**: Dedicated `gremio_territorios` tracking, GM assignment (`/settw <field> <guild_id>`, `/tw`), and event condition checks (28 `HAVE_GUILD_REGION`, 76 `SPEC_MAP_OWN_GUILD`, 82 `GUILD_MEMBER_TIME` $\ge$ 3 days).
  - **Old-style Totem War (field totems)**: the totem stands in the field itself (`0x012E`, format taken from a live capture), always visible to everyone and persistent across logins. It can only be damaged during the war, never by the faction that owns it; a neutral field can be hit by anyone. Breaking it without a league leaves the field neutral; a league only takes the territory if it qualifies. Faction emblem on the totem plate via `0x0131`. Training fields keep their own rules (Sunflower Plain 7, Foggy Forest 20, Mysterious Garden 22, Megalith Plain 28).
  - **Totem Offerings & Levels**: clicking your faction's totem opens the official window (`0x012F`); offered materials (`ofrendas_totem.json`) add points and level the totem up.
  - **PvP Fields**: the marked fields are PvP all day, with no warning prompt. Area skills hit rival players too. Kills count on the K.O. board (`0x001D` code 25) and give credits; dead players turn into a ghost until revived.
  - **Terra Keeper**: old-style dialogue showing the owning league; League Manor from the Heaven General goes to the Terra Keeper of the field.
  - **Heaven General (Tree 5920)**: Populated in all 4 cities, offering rank badge shop 71 (items 3735..3748), daily combat/production reward boxes (3776..3783, 9255..9258, 13409..13412), hidden daily token 3754, and territory teleport (`GOTO_GUILD_REGION`).
  - **Terra Keeper (Tree 5936) & Governor (Tree 5940)**: Gated entry to private territory areas (Area I stage 50, Area II stage 100, Area III stage 117, Area IV stage 377) and Thorn Wasteland stage 16 routing. Governor provides personal bank, guild vault, and Regression Scroll (3734).
- **Event Overview**: Online Bonus (daily minutes online, s2c `0x018A`) and Login Bonus (days logged this month, `0x016F`) with their Receive buttons (action 72 / 54), byte-identical to what the official server sent at login. Exchange's "Go to" (action 73) opens the shop of its group (`0x0151`). Event News opens a local page (`http://127.0.0.1:8280/news.htm`, news in `data/noticias.json`).
- **Angel Pass**: season Winter's Hymn Treasures, 60 levels, daily and weekly quests (monsters by race, farm, capture, fusion, ball, totem, login...), Claim / Purchase Lv / Purchase Premium Pass (action 74, s2c `0x018C`-`0x0194`). The client picks the season by the PC clock from its own `battlepass.xml`; all seasons had expired, so `update26.pak` gets that season's dates extended (agreed, like the rank medal).
- **Pet Amplify**: Unlock Slot (c2s `0x015D`, Amplify Hammers as in `pet_inlay.xml`) and Re-Amplify all / attribute / value (`0x015C`); the state packet `0x0179` is byte-identical to the official one. Inserting a pet into a slot is not done yet.
- **Gift boxes without a drop table** (1,766, e.g. Enchanted-Cozy Xmas Suitcase): opened from the list in their description ("Open to get:" gives all, "one of" gives one).
- **New titles without changing map**: the `0x0002` is resent (its handler does not load the map).
- **No `extracted_paks` needed**: on start, if it is missing, the server extracts the current `setting/*` files from the installed client's `.pak` (~250 MB, ~7 s, local only).
- **Totem respawn & training totems**: a broken totem comes back after 1 second with a NEW entity id (the old one was still dead in the client: slow to appear and without HP bar), as the monster type of its level (`monster.xml` 21397 "Totem Lv 1", 300,000 HP ... 21404 "Totem Lv 8") and back to level 1. The four training fields (Sunflower Plain, Foggy Forest, Mysterious Garden, Megalith Plain) show their decorative totem next to the Terra Keeper (positions from Celestia captures); it can never be damaged.
- **PvP damage**: separate formula from monsters, AO style `(ATK - DEF) x skill multiplier`, with the effective (buffed) defense of the target and its damage reduction from buffs and equipment (`物理/魔法傷害抵銷`). Combos hit all their hits, area combo skills (Bullet Arrow, Steel Rain...) play their animation once and finish in ~1.2 s, and the 71 spells flagged `不能對玩家施放` cannot hit players. Global tuning in `pvp_liga.FACTOR_PVP`.
- **Fusion system (WND_FUSE)**: C2S `0x0147` `[mode][main][assistant][potion][random]`, result via `0x001D` code 50 and pet preview via code 51 (all from REA). Consumables (10 + 10 + potion), equipment (one green attribute from the assistant) and pets (up to 3 bonuses, shapeshift into a new pet from the `fuse.xml` pet list with the Shape Fusion Potion 16074). Success rates for consumables/equipment are the client's own formulas; pet success uses a softened formula (`fusion.EXITO_MASCOTA_*`).
- **Achievements, titles & reputation**: the real `0x0155` (7,204 bytes: completion bits, % progress, score) on login and every map change; titles in the `0x0002` (+0x6d0 bits, +0x750 equipped), equip with action 49 / `0x001D` code 57, and a free Super BC the first time a title is obtained. 3,248 of the 4,351 achievements are tracked (level, skills, stats, monster kills, ranking top-N, quests, houses, fusion, pets, captures, enhancement, items, deaths, Totem War, days online...). Reputation = sum of the titles' `聲望值`; every `prestige.xml` level reached adds its fixed stats.
- **House deeds & items**: deeds (Cottage, Delicate House, Romantic Villa, Luxurious...) are the house size, never furniture: dropping one on the deed slot works like using it, they cannot go into furniture/pet/monster slots, and a login sanitizer fixes characters left inconsistent. Super Liquid Soap gives 2,500 cleanliness (cap 5,000). Fly Book / Summon Book (teleport to / summon a teammate), Spacious Iron Room (repair window), Spacious Bank / Guild Bank, and the revival scrolls (`使用公式` 10) now work.
- **Portals**: a step still pending from the previous map no longer fires a portal on the new map (South of Mirror Lake used to drop you in Spike Farm).
- **17 Dungeons & Instances Generated**: 17 instance map templates generated with parallel map execution, boss spawns, and guaranteed boss loot drops (Chaos bosses, Bashi's Gaze, quest progression drops).

**The customised client**

The server prepares the local client on startup, always taking a `.bak` first:

- **Angel Lyceum season** (normal, christmas, halloween, sakura, summer). It does not live in
  `map041.mpc` as was assumed, but in `stage.xml`: a **decoration** map (`裝飾地圖檔`) plus the
  weather. Switch it from the launcher, with `/estacion`, or via `MODO_ESTACION`
- **Nine skill slots** instead of six. The three extra ones open at **levels 301, 351 and 401**,
  with no Supreme Level and no quest, and fill themselves with a trade branch so you can swap it
  at the Skill Angel. Characters that do not yet have their base six are left untouched
- **No mutual exclusion between branches**: the eleven `互斥N` rules in `skill.xml` (Life↔Wraith,
  Chaos↔Earth, Meditate↔Enhance, Grapple↔Snipe and the Mantle/Garment/Vestment trio). The server
  never checked them; it was the client's picker that refused
- **Rank Promotion Medal** (83266), with each rank's credits read from the `功勳` column of
  `level.xml` and the rank banner (`0x0020` with `effect_id` 3)
- **Bound equipment NPC buyback data** patched across `item.xml` through `item9.xml`, preserving
  the no-player-trade flag while allowing eligible S/Fine rewards to be sold to shops
- **Launcher** in Spanish and English, with buttons to open several clients at once
- **Startup logo screen** blanked

**Partly**

- **Multiplayer Online Presence**: players see each other on map screens via official 128-byte `0x0001`, synchronize real-time movement (`0x0005`), transformations (`0x0013`), and companion combat actions. Complete third-party fashion skin overlays are still being refined.
- **Party / Teams System**: server recognizes and logs incoming team invitations (`0x0017`), but party acceptance handling, UI group bar, shared EXP, and member management (`0x0018`) are in progress.
- **Gold Cap / Gold Flag**: implemented, but thorough in-client testing is pending.
- NPC dialogue: 17 of the Lyceum's 52 NPCs have their text and options, plus
  expansion to regional and dungeon skill vendors.
- **Skills and spells**: melee combat, AoE spells, and magic trees are operational
  (casting, costs, damage, buffs, debuffs, summons, and progression). The longbow now lands
  its ranged basic (Basic Shot I, range 12); whether the arrow is drawn in flight is still
  unconfirmed, since the effect is only sent for skills. The dagger has had less testing.
- Spells: they show up on F1-F3, cast, buff and deal damage, but some visual
  effects are still missing.
- Physical and spell damage formulas now scale with linear defense mitigation
  and elemental stats, though extreme high levels (300+) or monsters with outlier
  attributes may still need fine calibration against packet captures.
- ~~Combos are read from `magic.xml` but never executed~~ **fixed**: all 475 run (376 direct
  via `連擊次數`, 99 chained via `轉嫁法術`), and the extra hits process the monster's death.
- The slow effect is registered but doesn't change movement speed.
- The staff and the axe use the sword's attack animation until someone
  captures theirs.
- Mounts equip to slot 10 and do speed you up, but not by the right amount:
  two different mounts that declare the same `move_speed` give different
  speeds in the real server, so what a mount contributes depends on its own
  instance, and that doesn't travel in `item.xml`.

- **Comprehensive Quest System (1,489 quests)**:
  - Complete quest catalog compiled from `quest.xml` with 1,489 quests and 662 repeatable quests.
  - Dynamic combat hunting tracking (877 automatic kill steps triggered by mob defeats across all maps with monster aliases and canonical naming).
  - Item collection objectives & **Hidden Quest Inventory**: regular collectable items drop into the visible bag, while Category `5001` quest tokens/credentials (such as *Work ID* 78179 or *Microcoin* 78180) route to hidden slot range `497..556`. Confirmed via disassembly of `Angel.exe`: `sub_4A48C0` (Prop window) strictly loops `20..94`, while `sub_4A47E0` (HUD tracker counter) and `sub_4A4720` (NPC turn-in check) iterate `20..154` and `497..556`. This allows HUD tracking progress (`1 / 1.`) and turn-in without cluttering the player's visible backpack.
  - Fixed NPC quest dialogue progression: UI option order matching official client, level requirement checks (e.g., Mr. Fleming in Wise Institute lv. 380, Leif in Sandy Heights), and continuous city commander quest chains.
  - NPC interaction & turn-in flow (over 1,500 delivery points and 1,100 quest-giving NPCs).
  - Repeatable, daily, and weekly rotating quest pools.
  - Automatic warps to quest instances / training arenas tied to specific quest stages.
  - Full persistence in SQLite and real-time client sync via opcodes `0x0021` and `0x0022`.
  - 100% stable quest abandonment and completion: disassembled `Angel.exe` (`sub_602BD0` / `0x004A5390`) and analyzed official packet traces (`mundo_180305_971213_orden.jsonl`) to send only `0x0022` mode 2 on abandon, eliminating `_invalid_parameter_noinfo` crashes and protecting against out-of-bounds backpack slots (> 60).

**Does not work**

- The ID Card draws the character in their underwear, even though the sprite
  in the world is dressed correctly. `0x0179`, the last suspect, was ruled
  out: its ids are hammers, not clothing (see below).
- Resources can't be gathered, so the nine skills tied to gathering and
  crafting never level up.
- Five of the Lyceum's NPCs were never captured and are missing.
- Passwords are **not validated**: the auth block hasn't been decrypted.
- The diving gate is **documented but not enforced**: both trainers, their
  dialogue and the two skills are captured, but the portal into the
  underwater maps still lets anyone through.
- Instances: nobody has been inside any of them. **Five entrances are
  identified and left switched off** -- Nightmare Palace, Half-beast Hamlet,
  Giant Wooden Stairs (which has two tornados leading to the same place) and
  Chocolate Forest. They sit in `portales.json` with their tile and their
  entity but with a null destination, and the server skips them, so standing
  on one does nothing. For Lost Region and Horrible Lost Region the entry
  dialogue, the two modes and the rejection messages are captured; their
  monsters are known from the wiki, their positions are not. Careful with one
  thing: that two-mode dialogue is **not** how instances are entered in
  general -- most ask nothing at all.
- Friend list system: documented from packet captures, but not yet implemented.

---

## The item catalogue

[`items.html`](items.html) is a single page listing **78,089 items** -- every
one in the client data, with its **id**, name, kind, group and icon. It is
built from the extracted client (UPDATE25) and from `corpus/content.db`, and
it needs no server and no connection: open the file and search.

It exists because the id is the one thing you cannot guess. The game never
shows it, and the tooling that hands out items takes the id and nothing else,
so anyone helping with drops, shops or testing ends up asking for the same
numbers over and over. This puts them all in one place.

The page weighs about 19 MB because the whole catalogue travels inside it, as
a JSON array the page filters in the browser. That is on purpose: a single
file that works offline is worth more here than a smaller one that needs
something running behind it.

`GM_ITEM_COMMAND_FOR_AI.md` is the spec for the in-game command that would use
those ids, written to be handed to an AI. **It is not implemented yet**: the
file describes what to reuse from `app.py` and how the command should parse,
and the server still has none of it.

---

## The three zones that came from elsewhere

Everything else in this project comes from captures of **a single** private
server. Twenty maps do not. They come from **a second server, on another
version of the client**, and it is worth knowing why and what it implies:

- **Night City Code**, stages 416 to 421 -- Clink Harbor, Neon Sky Corridor,
  Black Market District, Commercial Street, Bling Plaza and Ultimate Arena
- **Sun Sea Maze**, stages 397 to 402 -- Floating Station, Floral Alley,
  Majestic Mansion, Warm Villa, Verdant Shrine and Seaside Grotto
- **Cybertronica**, stages 405 to 410 -- Sandy Heights, Wise Institute, Clank
  Oasis, Ironbone Works, Machinery Ruins and Steely Circuit
- **Training Area A and B**, stages 118 and 134

The three zones share the same reason, told below with Night City Code
because that is where it was found first: on the main server the stages exist
but arrive empty. Seaside Grotto brought something extra, a teleport that is
not a portal: you **talk** to a statue and it moves you across the map. That
mechanism is described further down.

### Why another server was needed

The map had been in the client data since patch 25, and a tornado in Niro
River led to it. But crossing it, the server sent **7 entities and nothing
else**, all NPCs, all bunched in the (1..6, 1..5) corner. That is the
signature of a stage **declared but not populated**: it exists in the table,
it has no content. The portal sat measured but disabled, with a note saying
"enable it when some version brings the map populated".

The second server runs that version. Crossing the same tornado, it sends
**171 entities** spread across the whole map, with real monsters.
The map exists; what was missing was a server that served it.

### What was taken and what was not

The standing rule still holds: **take the DATA, never the raw bytes**. It
worked here because both speak the same language where it matters -- the
`0x0008` spawn message is **63 bytes in both versions**, with the fields in
the same places, and so is `MOVE_REQ`. The same code decodes it.

Where they do **not** match, and it needs keeping in mind:

- The `0x000C` map change arrives as **20 bytes with no IP string**, unlike
  ours. The stage still reads at offset 0, but the destination port is no
  longer where we expect it
- **Three messages we do not know** show up: `0x018A`, frequent and almost
  always eight bytes; `0x006D`, with an empty body; and `0x0142`, a single
  byte. None of them are in `proto/messages.py`

Names arrive in **Big5**, not English. Nothing had to be translated by hand:
the `npc_type` is the same in both versions, and our `content.db`, extracted
from the client XMLs, already carries the English name for every id. They are
matched through that.

### Two things that changed in the tools

**`tools/separar_por_mapa.py`** (new). On the other server every map change
opened a fresh connection, so each capture file covered a single map. Here the
`0x000C` arrives **inside the same session**: one connection brought six maps
in a row. Handing it whole to `poblar_mapa.py` would put one map's monsters
into another map's template, silently. This tool cuts by map change first.

**`tools/poblar_mapa.py`** decoded names as ASCII, which mangles Big5. It now
decodes Big5 -- ASCII-compatible, so nothing earlier changes -- and matches the
`npc_type` against `content.db` to leave the name in English.

### What was learned along the way

**Some map transitions have no tornado.** Five of the chain's thirteen portals
have no drawn object at all: you walk onto the tile and the map changes, with
nothing visible. Confirmed both in game and in the capture, where no object
sits anywhere near. **What triggers it is unknown**; it could be an invisible
portal. They were first called "edge crossings" and that was a wrong guess:
the maps are 300x180 and those tiles sit some eight columns short of the edge,
with entities even further out.

**A map can need several passes.** Commercial Street gave 71 monsters on the
first walk, 109 on the second and 125 on the third. The map did not change: a
capture only brings what you had in view, and the early passes left areas
uncovered.

**A teleport that is not a portal.** In Seaside Grotto you do not walk onto a
tornado: you **talk** to a statue. The click arrives as `0x0005`, the server
answers a `0x0012` dialogue with two options, the client sends `0x000B` with
`0a` -- option index 0, "Yes" -- and then comes a bare `0x0003` that moves the
character. No `0x000C`, so the map never reloads. It cost two wrong readings:
first the `0x000F` right after the dialogue was blamed, and that one turns up
95 times per session because it is a heartbeat. The way back is not a click at
all -- you step on the tornado -- and it sends only the `0x0003`, without the
`0x0016` and `0x0012` that the internal jumps of other maps carry.

### What is still missing from this region

Stage **422 (Secret Peak)** is still unpopulated. There is also Bling Plaza's
**instance entrance**, identified through `jumpmap.xml` -- it is the only one
of the chain's nine destinations carrying an extra class -- and **three
tornados in Ultimate Arena** that would not let the player through, most
likely gated by a quest or a level.

---

## What you need to run it

The repo is **self-contained**: it ships the 435 map templates, `content.db`,
`AO.db` and the tables derived from the client. **`extracted_paks/` is not
needed**, and is not published because it is IGG copyrighted material.

Verified by extracting `HEAD` into a clean folder and running from there.
Everything that depended on `extracted_paks` moved into templates: the credit
thresholds per rank (`creditos_rango.json`), the exclusion-free `skill.xml`
(`skill_sin_exclusion.xml.zlib`) and the seasonal decoration maps
(`mapas_estacion/*.zlib`).

The **client ships separately**, not in the repo.

---

## Running it

You need **Python 3.10 or newer** and the Angels Online client installed.
Tested against client **8.5.1.0**; the captures the protocol comes from were
taken with an **8.6.0.8**, and both speak the same thing.

IGG took the game down in February 2026, so the client is no longer available
from them. This is the copy this project is developed and tested against:

**[Angels Online client 8.5.1.0](https://drive.google.com/file/d/13IOcTJUkX7LfsznZ8tobyu5c5MuXjpZK/view?usp=sharing)**

It is IGG's client, unmodified. It is here because a protocol you cannot run
against anything is not much use, and because without it none of the
measurements in this repository can be reproduced.

1. Point the client at your machine, in its `server.xml`:

   ```xml
   <伺服器 名稱="Local" 編號="16" 選擇="100"
           ip="127.0.0.1" port="16768" 分流="2"
           fip="127.0.0.1" fport="21238" />
   ```

2. Start the server:

   ```
   ./correr_servidor.sh        # Linux, macOS, Git Bash
   correr_servidor.bat         # Windows
   ```

3. Open the client and log in with any username. The account is created for
   you.

Every session is recorded under `logs/sesiones/`, which is what you use to
debug.

### Environment variables

| Variable                | What it does                                                 |
| ----------------------- | ------------------------------------------------------------ |
| `AO_TILE`               | Spawn tile in Guide Palace (default `82,83`)                 |
| `AO_TILE_LYCEUM`        | Spawn tile in the Lyceum (`152,74`)                          |
| `AO_DURABILIDAD`        | Multiplies the durability of everything the server hands out |
| `AO_SECUENCIA_COMPLETA` | Sends the whole captured entry sequence, for comparison      |

---

## Layout

```
proto/        the protocol: framing, ciphers, message codec, LZO
server/       the server: login, world, inventory, combat, dialogue
server/plantillas/   blocks measured from real traffic, as JSON
tools/        capture proxy and analysis tools
docs/         everything that was worked out, and how it was verified
```

**Read `docs/01_HECHOS_VERIFICADOS.md` before touching anything.** It is over two thousand
lines covering every finding, how it was checked, and the mistakes made along
the way with their diagnosis. That last part is worth more than the code:
several things were taken as true from a single sample and turned out to be
wrong.

The documentation is in Spanish. The code and the commit history are too.

---

## The four tables that were hiding in the client

Four systems were guessed at for days before the data turned up inside the
client's own `.pak` files. None of them needed a formula: they are tables,
and the guesses were all wrong.

**`adv.xml` -- what the green hammer can give.** 2645 rows, by part and
level, with a floor and a ceiling for every stat. Two formulas had been
fitted to screenshots before this and both were wrong; what killed them was
using the same hammer on two pieces and getting different ranges. The table
matches the game exactly: a level 300 staff offers HP 344, attack 2428,
spell attack 697 and agility 30 -- which is what the client's own preview
box showed. It also settles the shape of the thing: a weapon never rolls
defence, armour never rolls attack, only a mount rolls movement speed, and
only a backpack rolls carry weight and extra slots.

**`pet.xml` -- 1751 pets.** Sprite, type id, name, which `petattrib` class
its stats come from, its evolution stage and its two branches. The type id
was going out as zero, and without it the client cannot tell which pet it is
looking at: the window came up with no level and no picture. The thirteen
sprite/type pairs seen in captures all match.

**`petaspect.xml` -- the breeding scenes.** 107 of them, three options each,
worth between -3 and +3. The text matches the game word for word.

**`jeweleffect.xml` -- what a gem does.** 870 rows. The numbers live on the
gem itself and this table says which stat they land on, and that depends on
where the gem is set: the same rune gives spell attack in a weapon and spell
defence in armour.

## Known issues

### The pet's own record is not saved

Everything else about pets works: the 231-byte inventory entry, the window
with its real stats, summoning and putting away, renaming, experience,
levelling and the whole evolution tree. But the pet's record lives only in
memory, so it resets to level 1 on every reconnect. The bag item persists;
what the pet has become does not.

### The breeding counter cannot be read

When a pet levels up the client shows a scene with three options and says
"(Your act affects Pet's growth)". That text is not sent over the wire: the
client picks the scene from its own `petaspect.xml` and only the chosen
option travels back, in `c2s 0x003E` with the values 4, 5 and 6 -- the same
message that carries pet orders with 0, 1 and 2.

So the server never learns which scene the player answered, and therefore
cannot tell what the answer was worth. Each of the 107 scenes has its own
three values, from -3 to +3. To close this the server has to pick the scene
itself and remember it, instead of letting the client choose.

### The ID Card draws the character undressed

The sprite walking around the world wears its gear correctly, but the figure
inside the ID Card panel shows the character in their underwear. The weapon
and the boots _are_ drawn there; it is the body garment that never applies.

**The last candidate was ruled out (2026-09-30).** `0x0179` had been carried
for a while as the message we were failing to send, with its ids
`40287..40295` taken for clothing sprites. They are not: those nine numbers
sit verbatim in `setting/pet_inlay.xml`, in the same order and the same
groups of three, and the file's own ALIAS calls them `ItemID` with
`Priority1/2/3`. Cross-referenced against `item.xml` they turn out to be
**hammers** — Hammer, Attribute Hammer and Value Hammer, each in a normal,
untradable and one-day variant. `0x0179` is a priority list of items for
socketing, a static table identical for everyone, and it draws nothing.

That closes out all four candidates: `0x0149`, `0x0179`, the character
record `0x0002`, and the skill-requirement correlation. The message that
redraws the figure **is not in anything captured so far**, so a capture
taken with the ID Card **open** while taking a body garment off and putting
it back on is still needed. What is no longer needed is the hunt for an
item → sprite table: there never was one.

### The damage formula drifts at high level

`attack x 33 / (33 + defence)` matches what a low-level character does. At
level 118 it is off by a factor of about 75. The relationship turned out to
be linear in defence rather than multiplicative, with a slope that depends on
the levels involved, and there aren't enough samples across level ranges to
pin it down.

### The staff and the axe attack animations

The `0x000A` carries a type and an animation number, and the pair depends on
the weapon. Measured by following the equipment changes inside each session:

| weapon                 | type | animation |
| ---------------------- | ---- | --------- |
| sword, dagger          | 3    | 1480      |
| spear                  | 2    | 827       |
| staff                  | 2    | 951       |
| two one-handed weapons | 2    | 832       |

The number is not a duration: the spear swings slower than the sword and yet
its number is lower. It selects which animation the client plays, so sending
the wrong one makes a spear attack as if it were dual wielding, with the
weapon not drawn at all. The staff and the axe still fall back to the sword's
pair, so a capture of someone attacking with them would finish the table.

### Screenshots of issues since fixed

The images under `docs/capturas/` are kept as a record. All five have been
resolved: the skill panel and the F1-F3 spells, NPC dialogue and movement,
opening boxes, the shop, and the floor teleport zones.

---

## What is deliberately skipped

So the server runs without a database or a sign-up flow, some things aren't
checked. These aren't bugs, they're decisions:

**Accounts create themselves.** Log in with any username and it gets saved to
`data/cuentas.json`. If you want to set one up by hand, it's plain JSON:

```json
{
  "cuentas": {
    "youruser": {
      "password": "whatever",
      "personajes": []
    }
  }
}
```

**Passwords are NOT validated.** Anything gets you in. The username is read
from the auth message, but the block carrying the password hasn't been
decrypted, so there's nothing to compare against. Finding that field was tried
twice and both attempts were wrong: one rejected valid logins, the other
accepted everything because the offset turned out to be a client-side
constant. It's documented in `server/cuentas.py`.

**There's no sign-up, no email, no recovery.** It's a local server.

### Visual glitches on reconnect

Some things look wrong until you log out and back in. Server and client end up
agreeing, but the client doesn't refresh on the spot:

- Music cuts out when changing maps
- The gear panel can be left with an extra slot drawn

Nothing gets corrupted: what's in `data/cuentas.json` is always correct.

---

## How to help

What's missing most isn't programming: it's **captures**.

Almost everything that doesn't work is missing because it was never recorded.
The proxy sits between the client and a working server, and logs both
directions with timestamps:

```
python tools/proxy.py --server-xml "path/to/server.xml"
# play for a while, doing whatever you want to capture
python tools/proxy.py --server-xml "path/to/server.xml" --restaurar
python tools/correlacionar.py --novedades
```

Two lessons that took several rounds to learn:

- **A capture only contains what you had on screen.** To populate a map you
  have to walk all of it, not stand in one spot.
- **Leave a couple of seconds between actions.** If they pile up, there's no
  way to tell which reply belongs to which request.

What would help right now, most useful first:

1. **Equipping a body garment with the ID Card open**, so the message that
   redraws the figure can be isolated. Still first on the list: with `0x0179`
   ruled out there is no candidate left in anything captured.
2. **Picking dialogue options** on several different NPCs. Five or six cases
   would fill in the 35 Lyceum NPCs that still have no text.
3. **Gathering a resource** with the right tool equipped. Nine skills depend
   on it and none of them can level up today.
4. **A long fight against monsters of several different levels**, with the
   levels of both sides written down, to pin the damage formula.
5. **Attacking with a staff and with an axe**, to finish the table of attack
   animations (sword, spear and dual wielding are already measured).

### Any kind of help

Everything is useful, and you don't need to know reverse engineering:

- **Traffic captures.** This is what's missing most. See above.
- **Code.** Pull requests are welcome. If you touch the protocol, say what you
  checked it against: this project rests on every claim having its
  verification behind it.
- **Client data.** If you find something in the `.xml` or `.pak` files that was
  written off as impossible here, say so. It has already happened twice that
  the data was right there.
- **Bug reports.** The server log plus what you did in the client is enough.
  The `logs/sesiones/` folder from that session helps a lot if you can share it.
- **Translations.** The documentation is in Spanish.
- **Just playing and telling us what breaks.** Half an hour in-game finds
  things that reading the code doesn't.

If you don't know where to start, open an issue and ask.

Before recording anything, check whether the data is already in the client's
XML files. It happened twice: spawn points were in `jumpmap.xml` and dialogue
in `msg.xml`, and captures were requested for things already on disk.

---

## Credits

This server was written from scratch, but it didn't start from nothing.

- **[AngelsOnlineDev/AO](https://github.com/AngelsOnlineDev/AO)** — the project
  that opened the way. No code was copied from it, but it was studied, and
  reading its log produced the finding that unblocked this whole project: the
  world redirect is sent **in reply to `0x0006`**, not after authentication.
  Weeks were spent stuck on that screen comparing bytes that were already
  correct; the problem was timing, not content.
- **Squirrel**, from RageZone — for trying first and leaving a trail. Someone
  having started and written something down, even without finishing, saves you
  the work of finding out which doors aren't worth opening.

And to whoever kept the client and its `.pak` files around. Without them there
would be nothing to rebuild: a good part of what works here came from reading
the game's own `.xml` files, not from traffic.

---

## Notice

Angels Online belongs to IGG. This is preservation work on a game that no
longer exists, done against a client anyone can install.

**Nothing of IGG's is included here**: not the client, not its data, not the
decompiled binary. The server reads the `.xml` and `.pak` files from a client
you already have; without one it does nothing and is of no use.

**No traffic captures are included either.** The ones used carried account
names and other people's public chat. The analysis lives in `docs/`; the raw
bytes aren't needed for anything. If you contribute captures, check the same
before uploading them.
