import json

p = 'server/plantillas/dialogos_npc.json'
d = json.load(open(p, encoding='utf-8'))

d['npcs']["Angels' Tutor"] = {
    "msgid": 10101,
    "val": 4,
    "hex": "7527000004000005007b2700007c2700007d2700007e2700007f270000",
    "texto": "/c$2%1/c*,I'm your tutor in the Angel Lyceum."
}
d['npcs']["Scroll Seller"] = {
    "msgid": 5628,
    "val": 4,
    "hex": "fc1500000400000200472f0000492f0000",
    "texto": "Hello, Little Angel, I'm the Angel Merchant who sells the Skill Scroll, if you want to learn some skills, you can buy one from me."
}
d['npcs']["Magic Seller"] = {
    "msgid": 5235,
    "val": 4,
    "hex": "731400000400000200472f0000492f0000",
    "texto": "Hello, Little Angel, I'm the Angel Merchant who sells the magic scrolls. If you want to learn more magic, you can buy one."
}
d['npcs']["C. Plan Seller"] = {
    "msgid": 5234,
    "val": 4,
    "hex": "721400000400000200472f0000492f0000",
    "texto": "Hello, Little Angel, I'm the Angel Merchant who sells the manufacture recipes. If you want to learn how to make things then you can buy one."
}
d['npcs']["Bao Clerk"] = {
    "msgid": 5236,
    "val": 4,
    "hex": "7414000004000003007514000076140000492f0000",
    "texto": "Which warehouse do you want to use?"
}

with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

print("dialogos_npc.json successfully updated!")

