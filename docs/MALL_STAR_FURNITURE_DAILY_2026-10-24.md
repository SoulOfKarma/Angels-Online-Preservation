# Item Mall, Star Blessing, furniture and Daily Events

## Catalog and original data

`tools/audit_item_mall_sources.py` and `tools/audit_recent_mall_sources.py`
reproduce their templates. The corrected catalog contains 457 listing candidates,
with at most 10 Top Sale entries selected at runtime.
Only original mall.xml products, replacements from existing dated class-bag
families and explicitly evidenced IGG Mall sales are included. Event bags,
bound bags, 5X stones, placeholder weapon boxes and individual nested prizes
are excluded. Taurus bags also populate their Weapon/Armor subtabs.
Native category23 is On Sale: box81972
is there at399 AG. Category22 ranks completed local purchases across all
listing categories over the last30 days; without history it features recent
verified products. This is not a recovered IGG best-seller ranking.
Royal Attendant, Bloodshadow Halloween and Holiday Gingerbread root bags also
appear in On Sale and Fashion Male/Female. Bubble40 offers the actual Halloween
bag containing the bubble; its nested bubble/vouchers are not sold separately.
Each root records its sale evidence. Royal is dated November6,2025; Gingerbread
is dated December4,2025 through January1,2026. Halloween's exact sale dates
remain unrecovered. These are local republications, not expired promotions.
No complete February2026 catalog was recovered. IGG's public archive ends in
December2025 and the December18 shopping article could not be retrieved.

The original475-row catalog remains the pricing reference. Dated promotions
through2022 are superseded; permanent utility prices remain. Each added price
records its provenance. Karma approved399 AG where no price can be recovered,
then requested the closest original price instead when available. The user's
IGG Mall screenshot explicitly shows200 Red/Blue Potion II for79 AG; other
potion grades use that same series reference, marked local. Initial AG is
unchanged: one million per account once, never a balance reset.

The catalog remains within the native packet boundary. Stable
listing IDs preserve the four previously introduced listings39000..39003;
Cabinet purchases already record their item/price independently of catalog
revisions. Removed products already owned by players remain openable with
their original contents; removal from sale never destroys existing stock.
`drop.xml` is incremental: the exporter merges numeric patch order, with the
English table winning within the same patch, rather than using only its final
file. This recovers four additional old boxes without fabricating contents.

The installation is the final available IGG content, through December2025.
Newer Angels Online Global advertisements use another client and item namespace;
their item IDs are not inserted into IGG. Taiwan's32 PAK revisions were also
searched read-only. Its mall.xml remains in data1.pak and does not supply IGG's
missing final catalog. No unrelated game items or prices were copied from it.

## Furniture

82599 Playful-Lizard Baby Egg uses drop28812: exactly one of73226..73230,
with native weights20 each. Opening is an atomic inventory transaction.
Received furniture stays in normal backpack stock and is tradable before use.
Right-clicking registers one unit into377..476, applies native owner binding,
persists inventory/metadata in one transaction and supplies an independent UID.
Registered stock is protected against sale, stalls, guild bank and moving back
to ordinary inventory. Direct dragging into Furniture uses the same registration.

Only registered stock can be placed. Tests place two different Lizard Babies,
save, reload and remove only one, retaining the other. Full registered storage,
stale inventory and SQL failure retain the original stock. Bulk `_meter`
preflights capacity before adding any furniture units.

## Pet portrait evidence

Dark Devil Egg61475 resolves to pet15553. Forest Devil Treesia15561 uses world
sprite44480 and portrait11507. Every evolution in this family retains11507 in
the original pet.xml. REA665890 selects that portrait from the actual pet ID;
0065 supplies the pet ID and leaves the optional portrait override zero.
The egg portrait under the stars is therefore original for this pet; the
evolved world sprite is a separate field. No arbitrary replacement was made.

## Star Blessing

REA59CBE0/59C700 sends015F(cmd,source,destination), including drag commands1..11.
59BF10 sends0160(group,index) for the Star exchange page, which must be routed
before generic NPC recipe handling. Generic action70 carries draw/convert/
upgrade/confirm commands. 6248A0 forwards S2C017F to module5, receiver6E7A70.
The length DWORD must equal payload length+4 (total packet length-2), not12.
Receiver6E7A70 stores field1 at module+60 (equipped matrix), field2 at+40
(Divination Outcome) and field3 at+20 (storage). The prior wrong mapping
displayed drawn cards as equipped even though the server had not equipped them.
Field5 stores Stardust first and Starforce second (getter6E83C0).
Native6EA13B writes the first DWORD to50052, whose original tooltip says
"Exchange Stardust for Perfect Star Sign". Bottom-left Coins is an actor
property, separate from this packet. Field7 contains five signed FREE DRAW
COUNTS (zero when none remain), nine sign kinds1..15 and their
marked flags, and the completed line count. It must not contain draw prices,
packed card IDs or a Bingo price. Field8 contains typed Bingo reward rows,
not balances. These corrections restore the tier badges, Bingo icons and
reward list visible in Karma's original IGG screenshots.
Matrix unlock count derives from100,160,200,240,280,320,360,400. State is sent
at login and again after world readiness.

`star_client.xml` has mixed node types and duplicate numeric IDs: parsing it
as a flat dictionary loses card rows to recipes. The separate exporter retains
all572 card rows and27 recipes. Packed IDs are rank*10000+kind*100+level,
using the original DEFINE mappings. Stat values, conversion and level-up costs,
and exchange materials are native. Equipment prevents duplicate sign types.
Stored, drawn, equipped and working cards, Starforce, Stardust and Bingo state
persist per account/character with optimistic validation and atomic gold/state
updates. Confirmation revalidates materials; replay cannot claim twice.

Original wnd01.xml tooltips50341..50345 give the Coin prices:
I1,000,000;II2,000,000;III4,000,000;IV8,000,000;V16,000,000.
Tier weights and next-level chance remain LOCAL compatibility settings in
`star_blessing.json`, not recovered official rates. I/II produce common signs;
III/IV can produce refined signs; V can also produce Stardust. Highest-rank
Olympian cards come from exchanges only. Action101 consumes one actual
backpack Star Key58283 (or native variants67178/69997/79859). Its native
description specifies Stardust or a Perfect Star Sign plus one free DivinationV:
one immediate outcome and one persisted V credit, not two immediate outcomes
or an extra storage slot. Key bonus weights75/25 are explicitly local.
Key, gold and card state commit together; missing keys, full outcomes or SQL
failure spend nothing. The current tier advances or returns toI; free IV/V
credits enable their respective tiers, rather than permanently unlocking all
tiers visited. Auto Divine commits and sends one card every0.3seconds and
stops when the20 outcome slots or Coins run out. Repeated clicks do not spawn
parallel draws. A completed Bingo does not block further divination, matching
the original Auto Divine tooltip. Auto Convert collects Stardust as dust and
other signs as their native Starforce value.

October25 correction from Karma's live comparison: native6E9D17 formats the
signed free-draw count even for an unavailable tier, so a negative sentinel
prints an incorrect "-1" badge. All exhausted counters now send0; native
availability still depends on current rank or a positive count. Collect
(action16) is allowed while Auto Divine is running. It settles the current
board atomically between draws without replacing/cancelling the task or
touching outcomes/Coins. Newly awarded freeIV credits apply to the next draw.
Repeated collection without new lines gives no reward and leaves the task
running. The focused Star suite passes47 tests, including both Starforce and
freeIV collection during Auto Divine. No live restart or visual validation
was performed for this correction.

Screenshot rewards transcribed without inventing the unseen7-line row:
1/2/3/4/5 lines give5/10/20/40/80 Starforce,6 lines give three freeIV draws,
8 lines give320 Starforce. Collection uses the highest applicable threshold
(local interpretation), then resets the board; replay cannot collect twice.
The Bingo Lucky Draw action consumes native item58284 and marks one unmarked
cell. It no longer charges a fabricated Coin price. Perfect recipes consume
20 Stardust; Olympian recipes consume their exact native Lv5 signs. All27
recipes are checked through preview, confirmation and repeat-claim rejection.
Known attack/defense/HP/MP/hit/evasion/critical/resistance stats feed the common
stat path. Specialized Olympian elemental attack, direct-damage and block
bonuses are represented in the template but still need their combat semantics
verified before claiming complete support for every Olympian attribute.

## Teleport consumables

`server/travel_items.py` handles the native item route before ordinary item use.
City scrolls resolve formula16 and the original destination revival tag61:
Building Blocks153, Pharaoh170 and Angelic Cave194, including equivalent
scrolls in the same native family. Mark Stone stores a persistent character
point; Mark Portal Scroll consumes one unit to return there. Maple Marks each
keep their own recorded location in item metadata, retain the mark and consume
one Maple Teleportation Scroll per return. Directly using an unrecorded return
scroll spends nothing. Witch Fly/Summon books select a current party member
and move the caller/member respectively. Destinations and inventory consumption
commit together; invalid event/private destinations or SQL failure spend
nothing. Same-map travel uses the native instant movement path without map
reload. Multi-member client portrait targeting still needs a live UI check.

## Daily Events

Daily Events Clerk8912, sprite40209, tile(161,93), direction7, portrait1009,
root504318 comes from `sp20111020.xml`. The final spmsg tree contains its
introduction, explanation, six original exchange groups296/297/345/299/346/347
and reward-status action108. Exchanges validate proximity/context/materials
and use the atomic inventory delivery path. Thirty-two old reward boxes still
lack complete original contents: those recipes are blocked BEFORE spending
coins and opening existing copies retains the box.

REA59AB30 requests C2S014B;6734F0 sends014A with a DWORD entry ID.
S2C0157 is74 bytes,18 DWORDs. Receiver6CBCB0 reorders fields15/16;6CC960 reads
the help string and6CC8E0 reads the entry command. Handler5F5DC0 compares the
received row count to packet+62 before rendering: this must contain the total,
not zero. The native renderer6CC45C formats row+28 before row+24, so wire+2A
is minimum level and wire+26 is maximum level. A test follows those consumers
instead of assuming wire order equals display order.

The client requests its timetable from the server with014B. Searches of the
installed IGG and Taiwan PAKs did not recover the original schedule. The old
seven-games-every-day placeholder is replaced by daily_schedule.json: two
distinct games daily at18:00/21:00 server local time,15-minute registration,
30-minute rounds,42 bracket rows weekly. This is a LOCAL rotation, not an
assertion about IGG's former hours. GM /daily start|enter|finish|stop <alias>
supports bleach, faction, guard, swindle, quick, joy and happiness;
/dailystart <alias> [minutes] [level] [registration_minutes] opens a manual round.

Example for a Lv434 test with immediate battle and no signup delay:

```text
/dailystart guard 30 434 0
/daily enter guard
/daily status guard
/daily finish guard
```

Replace guard with any alias above. Use registration_minutes1 to test signup
and the battle transition. `/dailystop guard` cancels instead of settling a
result. Starting a round does not teleport the GM: use enter separately.

All21 native map templates load their original generators, positioned guides
and resources. Shared room state persists across entrants. Bleach separates
teams, enables hostile flags for both clients, counts opposing kills and
respawns at team entrances. Faction uses original switches/Boom Slarm and
Baby Slarm objectives; players cannot damage babies or friendly bombs.
Guard and Swindle use native death events to unlock gates/release chests;
Swindle's original BATTLEFIELD_STATE46 and PK action107 are now interpreted.
October25 chest correction: ordinary GENERATE creates one actor per action,
but these Daily finite groups now use the native distributed template census
once per zone. Guard has batches10/20/20/20/150/150 (370 total across the
five guardians); Swindle has40 per chest zone. The exporter no longer caps
the two150-chest groups at40. All positions are distinct and walkable; other
maps retain the original one-per-GENERATE semantics. Released-zone IDs and
dead chest IDs persist with the round, so repeated death events/re-entry
cannot refill the group. Event999's GOTO_TAG is filtered from Daily chest
death effects instead of moving the killer back to the entrance. Other
monster/portal movement effects are retained.
Quick permits normal player attacks only. Joy uses original fast-respawn
generators and a local gathering speed bonus. Happiness releases native monster
rosters in waves toward the Goddess Tower instead of spawning every wave at
entry. Objectives and waiting rounds bypass ordinary wandering AI.

Round results and pending claims are journaled. Restart cancels unfinished
rooms without granting a defense win; settled claims survive. Winning players
present at completion receive one original level-tier Dailies Coin Bag through
the Clerk, once, in an atomic inventory/claim transaction. Ties and failed
defense give no winning bag. The one-bag quantity, wave interval/size, Joy
gathering bonus and controller timing are LOCAL compatibility settings;
original server values remain unavailable.32 old exchange boxes still lack
their original loot tables and remain blocked before consuming coins.

Compensation Angel71410009 is removed from both spawn list and dialogue tree.
Party Angel's native action54/14955 now applies the original12-hour
Archangel's Secret, including stat, EXP, Skill EXP, gathering, production and
drop bonuses. It refreshes without stacking and persists through death/relogin.

## Power Clone and Star summon correction (October25)

Native magic15281..15285, formula29, NPC6270 scales clone power75/80/85/90/100.
Power Clone now receives the player's combat orders, picks up the selected
target on creation and assists against an aggressor attacking its owner.
Dead, removed, charmed and protected Daily/Holy targets are rejected. Phantom
substitute6269 remains defensive. The snapshot uses effective owner stats,
including equipment, active transformations and passives: HP/MP, right/left
attack, defense, magic stats, accuracy, agility, critical and resistances.
Weapon range, movement and effective attack cadence replace generic NPC
defaults. Damage is credited to the owner and uses the normal monster death
pipeline, including Daily boss gate/chest effects. Clone attacks obey cadence,
range, travel time and line of sight; chase steps use walkable-map movement.

Star magic15378..15422 already selected the proper NPC22541..22585. A legacy
name conversion replaced a standalone English V with III. Only damaged Big5
pairs are repaired now; native Roman ranks are preserved. Tests verify all
five levels of all nine families, the exact NPC, native combat spell and
stronger V statistics. The observed Starchaos label was wrong even while its
NPC22580/attack83000/spell20489 were already rankV.

Directed regression for this correction:226 passed in32.42seconds,8 existing
asyncio fixture warnings. Covers actual clone damage/cooldown/death routing,
all45 Star spells, all Guard brackets, Swindle chests, map death events,
Olympus and Holy/Arena. Required compilation and diff whitespace checks pass.
No live server restart or in-client visual validation was performed.

## Verification and rollout

Temporary SQLite fixtures cover calendar receiver semantics, all seven map
entries, waiting/battle transitions, native boss death gates/chests, faction
rules, shared objectives, settlement/replay/full-inventory rollback, Star
receiver destinations and key transactions, Party Angel's actual menu buff,
and catalog provenance/exclusions. No live balances or inventory were reset.
The current directed regression passed265 tests in56.73seconds, including
Star, travel, Daily, furniture, Mall, Olympus and Holy/Arena regressions.
Nine existing asyncio fixture warnings remain. Required core-module and new
module compilation passed; `git diff --check` passed with line-ending warnings.
No server or client restart was performed and no in-client visual test is
claimed. Source/template changes require a controlled server restart to load.
