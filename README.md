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

## Actual state

**Works**

- Login, character creation, selection and deletion, saved to disk
- Entering the world, movement, changing maps, and floor teleport zones
- Angel Raphael's tutorial: picking a class, getting the gear, the transfer
- Inventory with **quantities**: consumables stack, and equipping, unequipping
  and moving between slots all report back per slot, the way the real server
  does
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
- **95 maps populated from captures**: 14,917 monsters, 1,149 NPCs and 8,951
  map objects, 5,029 of them with their resource name resolved. Every monster,
  NPC and resource comes from a capture; none of it is made up
- **Whole zones are closed**, meaning every tornado in them has been crossed
  and measured: **Heart of Eden**, **Floating** (6 maps), **the desert ring**
  (Crescent Valley, Desert Racetrack, Ghost Village, Troop Outpost, Ancient
  Front, Fantastic Sand City, Nightmare Palace) and **Candyland** (7 maps).
  **Atlantis is complete except for the instances**, and the forest chain
  (Cryptic Moon Swamp to Giant Wooden Stairs, 8 maps) only has two tornados
  left. Plus a good part of Pharaoh, East Orient and the four faction
  territories
- **208 portals**, almost all measured in both directions: the tornado's tile
  comes from the capture, and so does the tile the real server drops you on.
  Most of them were crossed **twice in each direction**, which is how we found
  out that some portals do not always drop you on the same tile
- **Angels GO!, the Superwing teleport**, works: `0x0151` carries the entry id
  from the client's own `jumpmap.xml`, a Superwing is spent, and the answer
  splits in two, both measured -- a `0x0003` when the destination is on the
  map you are already on, a `0x0007` plus `0x000C` when it is another map.
  The table has **355 destinations** and **140 of them are live**, the ones
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

**Partly**

- NPC dialogue: 17 of the Lyceum's 52 NPCs have their text and options
- **Skills are only really tested on three branches: Sword, Spear and
  Axe/Hammer (Warrior)**, and even there only partly -- they cast, hit and
  buff, but plenty is still missing. The **magic branches (Life, Wraith,
  Chaos, Earth) are not tested**: a player reported that a mage's spells
  failed on them, and that is not diagnosed yet. Longbow and Mantle have
  had no testing either. If you are trying this out, play a melee class
- Spells: they show up on F1-F3, cast, buff and deal damage, but some visual
  effects are still missing
- The damage formula holds up at low level and drifts badly at high level: it
  turned out to be linear in defence, and the coefficients depend on the
  levels of both sides
- Combos are read from `magic.xml` but never executed
- The slow effect is registered but doesn't change movement speed
- The staff and the axe use the sword's attack animation until someone
  captures theirs
- Mounts equip to slot 10 and do speed you up, but not by the right amount:
  two different mounts that declare the same `move_speed` give different
  speeds in the real server, so what a mount contributes depends on its own
  instance, and that doesn't travel in `item.xml`

**Does not work**

- The ID Card draws the character in their underwear, even though the sprite
  in the world is dressed correctly (see below)
- Resources can't be gathered, so the nine skills tied to gathering and
  crafting never level up
- Five of the Lyceum's NPCs were never captured and are missing
- Passwords are **not validated**: the auth block hasn't been decrypted
- Quests and whether you have spoken to Michael are **not saved to disk**:
  they survive the session and are lost on reconnect
- The diving gate is **documented but not enforced**: both trainers, their
  dialogue and the two skills are captured, but the portal into the
  underwater maps still lets anyone through
- Instances: nobody has been inside any of them. **Five entrances are
  identified and left switched off** -- Nightmare Palace, Half-beast Hamlet,
  Giant Wooden Stairs (which has two tornados leading to the same place) and
  Chocolate Forest. They sit in `portales.json` with their tile and their
  entity but with a null destination, and the server skips them, so standing
  on one does nothing. For Lost Region and Horrible Lost Region the entry
  dialogue, the two modes and the rejection messages are captured; their
  monsters are known from the wiki, their positions are not. Careful with one
  thing: that two-mode dialogue is **not** how instances are entered in
  general -- most ask nothing at all
- Parties and the friend list: the protocol is documented from a two-account
  capture, but the server does not implement either yet

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

## Known issues

### The ID Card draws the character undressed

The sprite walking around the world wears its gear correctly, but the figure
inside the ID Card panel shows the character in their underwear. The weapon
and the boots *are* drawn there; it is the body garment that never applies.

Three candidates were ruled out by measurement, so nobody needs to repeat
them: `0x0149` is byte-for-byte identical every single time, `0x0179` comes
out the same after every equip regardless of what you put on, and the
character record `0x0002` contains none of the equipped item ids — two logins
of the *same* character with different gear differ in only 56 bytes, all of
them stats and level.

What would settle it is a capture taken with the ID Card **open** while
taking a body garment off and putting it back on.

### The damage formula drifts at high level

`attack x 33 / (33 + defence)` matches what a low-level character does. At
level 118 it is off by a factor of about 75. The relationship turned out to
be linear in defence rather than multiplicative, with a slope that depends on
the levels involved, and there aren't enough samples across level ranges to
pin it down.

### The staff and the axe attack animations

The `0x000A` carries a type and an animation number, and the pair depends on
the weapon. Measured by following the equipment changes inside each session:

| weapon | type | animation |
| ------ | ---- | --------- |
| sword, dagger | 3 | 1480 |
| spear | 2 | 827 |
| staff | 2 | 951 |
| two one-handed weapons | 2 | 832 |

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
   redraws the figure can be isolated.
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
