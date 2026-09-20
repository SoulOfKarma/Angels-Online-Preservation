WND_BANK = 0
WND_BANKBAGS = {
  0,
  0,
  0,
  0,
  0,
  0
}
WND_BANKBAGS1 = 0
WND_BANKBAGS2 = 0
WND_BANKBAGS3 = 0
WND_BANKBAGS4 = 0
WND_BANKBAGS5 = 0
WND_BANKBAGS6 = 0
WND_BANK_X = -1
WND_BANK_Y = -1
WND_BANKBAGS1_X = -1
WND_BANKBAGS1_Y = -1
WND_BANKBAGS2_X = -1
WND_BANKBAGS2_Y = -1
WND_BANKBAGS3_X = -1
WND_BANKBAGS3_Y = -1
WND_BANKBAGS4_X = -1
WND_BANKBAGS4_Y = -1
WND_BANKBAGS5_X = -1
WND_BANKBAGS5_Y = -1
WND_BANKBAGS6_X = -1
WND_BANKBAGS6_Y = -1
WND_BANKBAGS7 = 0
WND_BANKBAGS8 = 0
WND_BANKBAGS9 = 0
WND_BANKBAGS10 = 0
WND_BANKBAGS11 = 0
WND_BANKBAGS12 = 0
WND_BANKBAGS13 = 0
WND_BANKBAGS14 = 0
WND_BANKBAGS15 = 0
WND_BANKBAGS16 = 0
WND_BANKBAGS17 = 0
WND_BANKBAGS18 = 0
WND_BANKBAGS19 = 0
WND_BANKBAGS20 = 0
WND_BANKBAGS21 = 0
WND_BANKBAGS22 = 0
WND_BANKBAGS23 = 0
WND_BANKBAGS24 = 0
WND_BANKBAGS7_X = -1
WND_BANKBAGS7_Y = -1
WND_BANKBAGS8_X = -1
WND_BANKBAGS8_Y = -1
WND_BANKBAGS9_X = -1
WND_BANKBAGS9_Y = -1
WND_BANKBAGS10_X = -1
WND_BANKBAGS10_Y = -1
WND_BANKBAGS11_X = -1
WND_BANKBAGS11_Y = -1
WND_BANKBAGS12_X = -1
WND_BANKBAGS12_Y = -1
WND_BANKBAGS13_X = -1
WND_BANKBAGS13_Y = -1
WND_BANKBAGS14_X = -1
WND_BANKBAGS14_Y = -1
WND_BANKBAGS15_X = -1
WND_BANKBAGS15_Y = -1
WND_BANKBAGS16_X = -1
WND_BANKBAGS16_Y = -1
WND_BANKBAGS17_X = -1
WND_BANKBAGS17_Y = -1
WND_BANKBAGS18_X = -1
WND_BANKBAGS18_Y = -1
WND_BANKBAGS19_X = -1
WND_BANKBAGS19_Y = -1
WND_BANKBAGS20_X = -1
WND_BANKBAGS20_Y = -1
WND_BANKBAGS21_X = -1
WND_BANKBAGS21_Y = -1
WND_BANKBAGS22_X = -1
WND_BANKBAGS22_Y = -1
WND_BANKBAGS23_X = -1
WND_BANKBAGS23_Y = -1
WND_BANKBAGS24_X = -1
WND_BANKBAGS24_Y = -1
BANK_TYPE_PERSONAL = 0
BANK_TYPE_GUILD = 1
CUR_BANK_TYPE = 0
DEFAULT_BANKBAGS_X = {
  0,
  0,
  202,
  202,
  202,
  202
}
DEFAULT_BANKBAGS_Y = {
  260,
  427,
  0,
  167,
  334,
  501
}
RES_BANKBAGS = {
  2276,
  2279,
  2282,
  2285,
  2288,
  2291
}
RES_BANKRENTS = {
  2277,
  2280,
  2283,
  2286,
  2289,
  2292
}
MAX_BANKBAG_NUM = 6
MAX_GUILDBANKBAG_NUM = 6
WND_RENT_BANK = 0
RENT_BANK_INDEX = 0
RENT_BANK_TIMER = 0
RENTBANK_1_DAY = 0
RENTBANK_7_DAY = 1
RENTBANK_30_DAY = 2
RENTBANK_FOREVER = 3
INIT_EXTEND_STORAGE2 = false

function InitExtendStorage2()
  MAX_BANKBAG_NUM = 24
  DEFAULT_BANKBAGS_X = {
    0,
    0,
    202,
    202,
    202,
    202,
    0,
    0,
    202,
    202,
    202,
    202,
    0,
    0,
    202,
    202,
    202,
    202,
    0,
    0,
    202,
    202,
    202,
    202
  }
  DEFAULT_BANKBAGS_Y = {
    260,
    427,
    0,
    167,
    334,
    501,
    260,
    427,
    0,
    167,
    334,
    501,
    260,
    427,
    0,
    167,
    334,
    501,
    260,
    427,
    0,
    167,
    334,
    501
  }
  RES_BANKBAGS = {
    2276,
    2279,
    2282,
    2285,
    2288,
    2291,
    2294,
    2297,
    24848,
    24851,
    24869,
    24887,
    24905,
    24923,
    24941,
    24959,
    24977,
    24995,
    25013,
    25031,
    25049,
    25067,
    25085,
    25103
  }
  RES_BANKRENTS = {
    2277,
    2280,
    2283,
    2286,
    2289,
    2292,
    2295,
    2298,
    24849,
    24852,
    24870,
    24888,
    24906,
    24924,
    24942,
    24960,
    24978,
    24996,
    25014,
    25032,
    25050,
    25068,
    25086,
    25104
  }
  WND_BANKBAGS = {
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0
  }
  INIT_EXTEND_STORAGE2 = true
end

function CreateBankWnd(nBankType)
  local w, bankResID, guildBankIconID
  if game.isdef("__EXTEND_STORAGE2") == true then
    if INIT_EXTEND_STORAGE2 == false then
      InitExtendStorage2()
    end
    bankResID = 25121
    guildBankIconID = 2103
  else
    bankResID = 2100
    guildBankIconID = 2101
  end
  if window.isexist(WND_BANK) then
    DestroyBankWnd()
  end
  if game.isdef("__PAD_CONTROL") == true then
    ShowCommand(true)
  end
  if nBankType == BANK_TYPE_PERSONAL then
    WND_BANK = window.create(bankResID, 0, 0, SYSTEM_HANDLER)
    window.settitle(WND_BANK, game.getstring(684))
    if game.isdef("__EXTEND_STORAGE2") == true then
      if game.isdef("__JAPAN") == true then
        for i = 1, 4 do
          window.seticon(window.find(WND_BANK, 24838 + i - 1), 2265)
        end
        for i = 1, 6 do
          window.seticon(window.find(WND_BANK, 24842 + i - 1), 2266)
        end
      else
        for i = 1, 18 do
          window.seticon(window.find(WND_BANK, 24830 + i - 1), 2265)
        end
      end
    end
  elseif nBankType == BANK_TYPE_GUILD then
    WND_BANK = window.create(2100, 0, 0, SYSTEM_HANDLER)
    window.seticon(WND_BANK, guildBankIconID)
    window.settitle(WND_BANK, game.getstring(685))
    for i = 1, 6 do
      window.enable(window.find(WND_BANK, 2264 + i - 1), game.canusebankbag(BANK_TYPE_GUILD, i))
    end
  end
  if 0 > WND_BANK_X or 0 > WND_BANK_Y then
    window.move(WND_BANK, 0, 0)
  else
    window.move(WND_BANK, WND_BANK_X, WND_BANK_Y)
  end
  CUR_BANK_TYPE = nBankType
  game.initbankwnd(WND_BANK, CUR_BANK_TYPE, 0)
  window.regsetting(WND_BANK, "WND_BANK")
  if window.isexist(WND_TRADE) then
    window.enable(window.find(WND_BANK, 3039), false)
  end
  return 1
end

function DestroyBankWnd()
  if window.isexist(WND_BANK) then
    window.destroy(WND_BANK)
    WND_BANK = 0
    local maxNum
    if CUR_BANK_TYPE == BANK_TYPE_PERSONAL then
      maxNum = MAX_BANKBAG_NUM
    else
      maxNum = MAX_GUILDBANKBAG_NUM
    end
    for i = 1, maxNum do
      if window.isexist(WND_BANKBAGS[i]) then
        window.destroy(WND_BANKBAGS[i])
        WND_BANKBAGS[i] = 0
      end
    end
    if window.isexist(WND_ITEM) then
      window.enable(window.find(WND_ITEM, 3036), false)
    end
  end
  if window.isexist(WND_RENT_BANK) then
    window.destroy(WND_RENT_BANK)
    WND_RENT_BANK = 0
  end
end

function GetBankBagWnd(nth)
  local maxNum
  if CUR_BANK_TYPE == BANK_TYPE_PERSONAL then
    maxNum = MAX_BANKBAG_NUM
  else
    maxNum = MAX_GUILDBANKBAG_NUM
  end
  if 1 <= nth and nth <= maxNum then
    return WND_BANKBAGS[nth]
  else
    return 0
  end
end

function MoveBankBag(nth, dwWndID)
  local x, y
  if nth == 1 then
    x = WND_BANKBAGS1_X
    y = WND_BANKBAGS1_Y
    WND_BANKBAGS1 = dwWndID
  elseif nth == 2 then
    x = WND_BANKBAGS2_X
    y = WND_BANKBAGS2_Y
    WND_BANKBAGS2 = dwWndID
  elseif nth == 3 then
    x = WND_BANKBAGS3_X
    y = WND_BANKBAGS3_Y
    WND_BANKBAGS3 = dwWndID
  elseif nth == 4 then
    x = WND_BANKBAGS4_X
    y = WND_BANKBAGS4_Y
    WND_BANKBAGS4 = dwWndID
  elseif nth == 5 then
    x = WND_BANKBAGS5_X
    y = WND_BANKBAGS5_Y
    WND_BANKBAGS5 = dwWndID
  elseif nth == 6 then
    x = WND_BANKBAGS6_X
    y = WND_BANKBAGS6_Y
    WND_BANKBAGS6 = dwWndID
  elseif nth == 7 then
    x = WND_BANKBAGS7_X
    y = WND_BANKBAGS7_Y
    WND_BANKBAGS7 = dwWndID
  elseif nth == 8 then
    x = WND_BANKBAGS8_X
    y = WND_BANKBAGS8_Y
    WND_BANKBAGS8 = dwWndID
  elseif nth == 9 then
    x = WND_BANKBAGS9_X
    y = WND_BANKBAGS9_Y
    WND_BANKBAGS9 = dwWndID
  elseif nth == 10 then
    x = WND_BANKBAGS10_X
    y = WND_BANKBAGS10_Y
    WND_BANKBAGS10 = dwWndID
  elseif nth == 11 then
    x = WND_BANKBAGS11_X
    y = WND_BANKBAGS11_Y
    WND_BANKBAGS11 = dwWndID
  elseif nth == 12 then
    x = WND_BANKBAGS12_X
    y = WND_BANKBAGS12_Y
    WND_BANKBAGS12 = dwWndID
  elseif nth == 13 then
    x = WND_BANKBAGS13_X
    y = WND_BANKBAGS13_Y
    WND_BANKBAGS13 = dwWndID
  elseif nth == 14 then
    x = WND_BANKBAGS14_X
    y = WND_BANKBAGS14_Y
    WND_BANKBAGS14 = dwWndID
  elseif nth == 15 then
    x = WND_BANKBAGS15_X
    y = WND_BANKBAGS15_Y
    WND_BANKBAGS15 = dwWndID
  elseif nth == 16 then
    x = WND_BANKBAGS16_X
    y = WND_BANKBAGS16_Y
    WND_BANKBAGS16 = dwWndID
  elseif nth == 17 then
    x = WND_BANKBAGS17_X
    y = WND_BANKBAGS17_Y
    WND_BANKBAGS17 = dwWndID
  elseif nth == 18 then
    x = WND_BANKBAGS18_X
    y = WND_BANKBAGS18_Y
    WND_BANKBAGS18 = dwWndID
  elseif nth == 19 then
    x = WND_BANKBAGS19_X
    y = WND_BANKBAGS19_Y
    WND_BANKBAGS19 = dwWndID
  elseif nth == 20 then
    x = WND_BANKBAGS20_X
    y = WND_BANKBAGS20_Y
    WND_BANKBAGS20 = dwWndID
  elseif nth == 21 then
    x = WND_BANKBAGS21_X
    y = WND_BANKBAGS21_Y
    WND_BANKBAGS21 = dwWndID
  elseif nth == 22 then
    x = WND_BANKBAGS22_X
    y = WND_BANKBAGS22_Y
    WND_BANKBAGS22 = dwWndID
  elseif nth == 23 then
    x = WND_BANKBAGS23_X
    y = WND_BANKBAGS23_Y
    WND_BANKBAGS23 = dwWndID
  elseif nth == 24 then
    x = WND_BANKBAGS24_X
    y = WND_BANKBAGS24_Y
    WND_BANKBAGS24 = dwWndID
  else
    x = DEFAULT_BANKBAGS_X[nth]
    y = DEFAULT_BANKBAGS_Y[nth]
  end
  window.move(dwWndID, x, y)
end

function OnOpenBankBag(dwID, dwCmdID, dwParam, pParam)
  local nth
  nth = window.getappdata(dwID)
  if window.isexist(WND_BANKBAGS[nth]) then
    window.destroy(WND_BANKBAGS[nth])
    WND_BANKBAGS[nth] = 0
    return 1
  end
  WND_BANKBAGS[nth] = window.create(RES_BANKBAGS[nth], 0, 0, SYSTEM_HANDLER)
  MoveBankBag(nth, WND_BANKBAGS[nth])
  if CUR_BANK_TYPE == BANK_TYPE_PERSONAL then
    if game.isbankrent(nth) then
      window.enable(window.find(WND_BANKBAGS[nth], RES_BANKRENTS[nth]), false)
    else
      window.enable(window.find(WND_BANKBAGS[nth], RES_BANKRENTS[nth]), true)
    end
    if game.isdef("__EXTEND_STORAGE2") == true and game.isdef("__JAPAN") == true and 15 <= nth and nth <= 18 then
      window.show(window.find(WND_BANKBAGS[nth], RES_BANKRENTS[nth]), false)
      window.show(window.find(WND_BANKBAGS[nth], RES_BANKRENTS[nth] + 1), false)
    end
  else
    window.enable(window.find(WND_BANKBAGS[nth], RES_BANKRENTS[nth]), false)
  end
  game.initbankwnd(WND_BANKBAGS[nth], CUR_BANK_TYPE, nth)
  window.regsetting(WND_BANKBAGS[nth], "WND_BANKBAGS" .. nth)
  return 1
end

function OnDragBankItem(dwID, dwCmdID, dwParam, pParam)
  game.dragbankitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropBankItem(dwID, dwCmdID, dwParam, pParam)
  game.dropbankitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnUseBankItem(dwID, dwCmdID, dwParam, pParam)
  local slot
  slot = game.getitemslot(dwCmdID)
  if 0 < slot then
    game.usebankitem(slot)
  end
  return 1
end

function OnCloseBank(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_BANK) then
    game.closebank()
    DestroyBankWnd()
  end
  return 1
end

WND_SPLIT_MONEY = 0
RES_SPLIT_MONEY = 0

function OnShowSplitMoneyWnd(dwID, dwCmdID, dwParam, pParam)
  local x, y, w, nMax
  if window.isexist(WND_SPLIT_MONEY) then
    window.destroy(WND_SPLIT_MONEY)
    WND_SPLIT_MONEY = 0
    RES_SPLIT_MONEY = 0
    return 1
  end
  WND_SPLIT_MONEY = window.create(2880, 0, 0, SYSTEM_HANDLER)
  RES_SPLIT_MONEY = dwCmdID
  x = window.left(dwID)
  y = window.top(dwID) - window.height(WND_SPLIT_MONEY) - 2
  window.move(WND_SPLIT_MONEY, x, y)
  nMax = game.getmoney(dwCmdID)
  w = window.find(WND_SPLIT_MONEY, 2882)
  window.setminnumber(w, 0)
  window.setmaxnumber(w, nMax)
  window.settitleint(w, nMax)
  w = window.find(WND_SPLIT_MONEY, 2883)
  window.setrange(w, 0, nMax)
  window.setpos(w, nMax)
  return 1
end

function OnSplitMoney(dwID, dwCmdID, dwParam, pParam)
  local w, num
  w = window.find(window.parent(dwID), 2882)
  num = window.gettitleint(w)
  if 0 < num then
    game.setsplitmoneynum(num)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnEditMoneyNumber(dwID, dwCmdID, dwParam, pParam)
  local w, num
  num = window.gettitleint(dwID)
  w = window.find(window.parent(dwID), 2883)
  window.setpos(w, num)
  return 1
end

function OnScrollMoneyNumber(dwID, dwCmdID, dwParam, pParam)
  local w, num
  num = window.getpos(dwID)
  w = window.find(window.parent(dwID), 2882)
  window.settitleint(w, num)
  return 1
end

function OnCancelSplitMoney(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnShowRentBank(dwID, dwCmdID, dwParam, pParam)
  local b1, b7, b30, bforever
  if CUR_BANK_TYPE == BANK_TYPE_PERSONAL then
    if window.isexist(WND_RENT_BANK) then
      window.destroy(WND_RENT_BANK)
    end
    WND_RENT_BANK = window.create(867, 0, 0, SYSTEM_HANDLER)
    RENT_BANK_INDEX = window.getappdata(dwID)
    RENT_BANK_TIMER = window.getclock()
    b1 = game.hasbankkey(RENTBANK_1_DAY)
    b7 = game.hasbankkey(RENTBANK_7_DAY)
    b30 = game.hasbankkey(RENTBANK_30_DAY)
    bforever = game.hasbankkey(RENTBANK_FOREVER)
    if game.isdef("__EXTEND_STORAGE2") == true then
      if game.isdef("__JAPAN") == true then
        if RENT_BANK_INDEX >= 18 and RENT_BANK_INDEX <= 23 then
          b1 = false
          b7 = false
          b30 = false
        end
      elseif RENT_BANK_INDEX >= 6 and RENT_BANK_INDEX <= 23 then
        b1 = false
        b7 = false
        b30 = false
      end
    end
    window.show(window.find(WND_RENT_BANK, 868), b1)
    window.show(window.find(WND_RENT_BANK, 872), b1)
    window.show(window.find(WND_RENT_BANK, 869), b7)
    window.show(window.find(WND_RENT_BANK, 873), b7)
    window.show(window.find(WND_RENT_BANK, 870), b30)
    window.show(window.find(WND_RENT_BANK, 874), b30)
    window.show(window.find(WND_RENT_BANK, 876), bforever)
    window.show(window.find(WND_RENT_BANK, 877), bforever)
    if bforever == true then
      window.setradio(window.find(WND_RENT_BANK, 868), 3)
    end
    if b30 == true then
      window.setradio(window.find(WND_RENT_BANK, 868), 2)
    end
    if b7 == true then
      window.setradio(window.find(WND_RENT_BANK, 868), 1)
    end
    if b1 == true then
      window.setradio(window.find(WND_RENT_BANK, 868), 0)
    end
    if b1 == true or b7 == true or b30 == true or bforever == true then
      window.enable(window.find(WND_RENT_BANK, 875), true)
    else
      window.enable(window.find(WND_RENT_BANK, 875), false)
    end
  end
  return 1
end

function OnSendRentBank(dwID, dwCmdID, dwParam, pParam)
  local sel
  sel = window.getradio(window.find(WND_RENT_BANK, 868))
  game.sendrentbank(RENT_BANK_INDEX, sel)
  window.destroy(WND_RENT_BANK)
  WND_RENT_BANK = 0
  return 1
end

function OnUpdateBankBag(dwID, dwCmdID, dwParam, pParam)
  if CUR_BANK_TYPE == BANK_TYPE_PERSONAL and window.getclockdur(RENT_BANK_TIMER, window.getclock()) > 1000 then
    local index = window.getappdata(dwID)
    window.settitle(dwID, game.getbankbagmsg(index))
    if game.isdef("__EXTEND_STORAGE2") == true and window.gettitle(dwID) == game.getstring(919) then
      window.show(window.find(WND_BANKBAGS[index + 1], RES_BANKRENTS[index + 1]), false)
    end
    RENT_BANK_TIMER = window.getclock()
  end
  return 1
end
