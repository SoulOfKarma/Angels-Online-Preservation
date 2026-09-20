AS_BOL_ISBACK_NOHPITEM = 1500
AS_BOL_ISBACK_NOMPITEM = 1501
AS_BOL_ISBACK_BROKENEQ = 1502
AS_BOL_ISBACK_NOBULLET = 1503
AS_BOL_ISBACK_NOSPACE = 1504
AS_INT_CARRYBOUND = 1505
AS_INT_SPACEBOUND = 1506
AS_INT_BACKTOWNITEM = 1507
AS_BOL_ISREPAIR = 1508
AS_BOL_ISRECALLFIGHT = 1509
AS_INT_WAITINGTIME = 1510
AS_BOL_ISBUYITEM = 1511
AS_INTLIST_TOBUYID = 1512
AS_BOL_ISDISCARD = 1513
AS_BOL_ISDEPOSITGOLDITEM = 1514
AS_BOL_ISDEPOSITGOODITEM = 1515
AS_STRLIST_TODISCARD = 1516
AS_INTLIST_TOBUYNUM = 1517
AS_INTLIST_TODISCARD = 1518
AS_BOL_ISMODIFIED = 1519
AS_BOL_ROBORCALL = 1520
AS_BOL_ISMODIFIED_V2 = 1521
AS_BOL_CONTINUEEXERCISE = 1522
HANDLETYPE_REMOVE = 0
HANDLETYPE_DEPOSIT = 1
HANDLETYPE_SALE = 2
HANDLETYPE_DISCARD = 3
MAX_SHOOPINGNUM = 8000
ENABLE_SUPPLYPROCESS = 0
WND_AUTOSUPPLYMINIPACK = 0
AS_VARIABLE_BUY_LIST_ARROW_ITEM_NUM = 0

function Init_insertautosupply_buylist(itemID, isArrow, oldItemTable)
  game.robotvar_add_intlist(AS_INTLIST_TOBUYID, itemID)
  if oldItemTable ~= nil and oldItemTable[itemID] ~= nil and 0 < oldItemTable[itemID] then
    game.robotvar_add_intlist(AS_INTLIST_TOBUYNUM, oldItemTable[itemID])
  else
    game.robotvar_add_intlist(AS_INTLIST_TOBUYNUM, 0)
  end
  if isArrow == true then
    AS_VARIABLE_BUY_LIST_ARROW_ITEM_NUM = AS_VARIABLE_BUY_LIST_ARROW_ITEM_NUM + 1
  end
end

function Init_autosupplyreloadtobuylist()
  if game.isdef("__TAIWAN") or game.isdef("__CHINA") or game.isdef("__USA") or game.isdef("__MALAYSIA") or game.isdef("__INDONESIA") or game.isdef("__KOREA") or game.isdef("__JAPAN") then
    local numItem = game.robotvar_getnum_list(AS_INTLIST_TOBUYID)
    local oldItemTable = {}
    for i = 0, numItem - 1 do
      oldItemTable[game.getrobotvar_intlist(AS_INTLIST_TOBUYID, i)] = game.getrobotvar_intlist(AS_INTLIST_TOBUYNUM, i)
    end
    game.robotvar_clear_list(AS_INTLIST_TOBUYID)
    game.robotvar_clear_list(AS_INTLIST_TOBUYNUM)
    AS_VARIABLE_BUY_LIST_ARROW_ITEM_NUM = 0
    Init_insertautosupply_buylist(2, false, oldItemTable)
    Init_insertautosupply_buylist(1228, false, oldItemTable)
    Init_insertautosupply_buylist(66, false, oldItemTable)
    Init_insertautosupply_buylist(1352, false, oldItemTable)
    Init_insertautosupply_buylist(1354, false, oldItemTable)
    Init_insertautosupply_buylist(1356, false, oldItemTable)
    if game.isdef("__USA") == true then
      if game.isdef("__DATA18") then
        Init_insertautosupply_buylist(1358, false, oldItemTable)
      end
    elseif game.isdef("__DATA25") then
      Init_insertautosupply_buylist(1358, false, oldItemTable)
    end
    Init_insertautosupply_buylist(67, false, oldItemTable)
    Init_insertautosupply_buylist(1353, false, oldItemTable)
    Init_insertautosupply_buylist(1355, false, oldItemTable)
    Init_insertautosupply_buylist(1357, false, oldItemTable)
    if game.isdef("__USA") == true then
      if game.isdef("__DATA18") then
        Init_insertautosupply_buylist(1359, false, oldItemTable)
      end
    elseif game.isdef("__DATA25") then
      Init_insertautosupply_buylist(1359, false, oldItemTable)
    end
    Init_insertautosupply_buylist(1905, false, oldItemTable)
    Init_insertautosupply_buylist(138, true, oldItemTable)
    Init_insertautosupply_buylist(361, true, oldItemTable)
    Init_insertautosupply_buylist(811, true, oldItemTable)
    Init_insertautosupply_buylist(362, true, oldItemTable)
    Init_insertautosupply_buylist(364, true, oldItemTable)
    Init_insertautosupply_buylist(363, true, oldItemTable)
    Init_insertautosupply_buylist(365, true, oldItemTable)
    Init_insertautosupply_buylist(4048, true, oldItemTable)
    Init_insertautosupply_buylist(4052, true, oldItemTable)
    Init_insertautosupply_buylist(5190, true, oldItemTable)
    Init_insertautosupply_buylist(5194, true, oldItemTable)
    Init_insertautosupply_buylist(7060, true, oldItemTable)
    Init_insertautosupply_buylist(7538, true, oldItemTable)
    Init_insertautosupply_buylist(9729, true, oldItemTable)
    Init_insertautosupply_buylist(7542, true, oldItemTable)
    Init_insertautosupply_buylist(9733, true, oldItemTable)
    Init_insertautosupply_buylist(11014, true, oldItemTable)
    Init_insertautosupply_buylist(13649, true, oldItemTable)
    Init_insertautosupply_buylist(13665, true, oldItemTable)
    Init_insertautosupply_buylist(13681, true, oldItemTable)
    Init_insertautosupply_buylist(13697, true, oldItemTable)
    Init_insertautosupply_buylist(16325, true, oldItemTable)
    Init_insertautosupply_buylist(16344, true, oldItemTable)
    Init_insertautosupply_buylist(16363, true, oldItemTable)
    Init_insertautosupply_buylist(16382, true, oldItemTable)
    Init_insertautosupply_buylist(18968, true, oldItemTable)
    Init_insertautosupply_buylist(18987, true, oldItemTable)
    Init_insertautosupply_buylist(19006, true, oldItemTable)
    Init_insertautosupply_buylist(19025, true, oldItemTable)
    Init_insertautosupply_buylist(21455, true, oldItemTable)
    Init_insertautosupply_buylist(21474, true, oldItemTable)
    Init_insertautosupply_buylist(21493, true, oldItemTable)
    Init_insertautosupply_buylist(21512, true, oldItemTable)
    Init_insertautosupply_buylist(23131, true, oldItemTable)
    Init_insertautosupply_buylist(23150, true, oldItemTable)
    Init_insertautosupply_buylist(23169, true, oldItemTable)
    Init_insertautosupply_buylist(23188, true, oldItemTable)
    Init_insertautosupply_buylist(25845, true, oldItemTable)
    Init_insertautosupply_buylist(25864, true, oldItemTable)
    Init_insertautosupply_buylist(25883, true, oldItemTable)
    Init_insertautosupply_buylist(25902, true, oldItemTable)
    Init_insertautosupply_buylist(27516, true, oldItemTable)
    Init_insertautosupply_buylist(27535, true, oldItemTable)
    Init_insertautosupply_buylist(27554, true, oldItemTable)
    Init_insertautosupply_buylist(27573, true, oldItemTable)
    Init_insertautosupply_buylist(30013, true, oldItemTable)
    Init_insertautosupply_buylist(30032, true, oldItemTable)
    Init_insertautosupply_buylist(30051, true, oldItemTable)
    Init_insertautosupply_buylist(30070, true, oldItemTable)
    Init_insertautosupply_buylist(33285, true, oldItemTable)
    Init_insertautosupply_buylist(33304, true, oldItemTable)
    Init_insertautosupply_buylist(33323, true, oldItemTable)
    Init_insertautosupply_buylist(33342, true, oldItemTable)
    Init_insertautosupply_buylist(37045, true, oldItemTable)
    Init_insertautosupply_buylist(37064, true, oldItemTable)
    Init_insertautosupply_buylist(37083, true, oldItemTable)
    Init_insertautosupply_buylist(37102, true, oldItemTable)
    Init_insertautosupply_buylist(40613, true, oldItemTable)
    Init_insertautosupply_buylist(40632, true, oldItemTable)
    Init_insertautosupply_buylist(41713, true, oldItemTable)
    Init_insertautosupply_buylist(41732, true, oldItemTable)
    Init_insertautosupply_buylist(41751, true, oldItemTable)
    Init_insertautosupply_buylist(41770, true, oldItemTable)
    if game.isdef("__DATA19") then
      Init_insertautosupply_buylist(45969, true, oldItemTable)
      Init_insertautosupply_buylist(45988, true, oldItemTable)
    end
    if game.isdef("__DATA20") then
      Init_insertautosupply_buylist(48813, true, oldItemTable)
      Init_insertautosupply_buylist(48832, true, oldItemTable)
    end
    if game.isdef("__DATA21") then
      Init_insertautosupply_buylist(53109, true, oldItemTable)
      Init_insertautosupply_buylist(53128, true, oldItemTable)
    end
    if game.isdef("__DATA22") then
      Init_insertautosupply_buylist(56564, true, oldItemTable)
      Init_insertautosupply_buylist(56583, true, oldItemTable)
    end
    if game.isdef("__DATA23") then
      Init_insertautosupply_buylist(58521, true, oldItemTable)
      Init_insertautosupply_buylist(58540, true, oldItemTable)
    end
    if game.isdef("__DATA24") then
      Init_insertautosupply_buylist(64358, true, oldItemTable)
      Init_insertautosupply_buylist(66554, true, oldItemTable)
    end
    if game.isdef("__DATA25") then
      Init_insertautosupply_buylist(69579, true, oldItemTable)
      Init_insertautosupply_buylist(69652, true, oldItemTable)
    end
    if game.isdef("__DATA26") then
      Init_insertautosupply_buylist(71598, true, oldItemTable)
    end
    if game.isdef("__DATA27") then
      Init_insertautosupply_buylist(74663, true, oldItemTable)
    end
    if game.isdef("__DATA28") then
      Init_insertautosupply_buylist(77747, true, oldItemTable)
    end
    if game.isdef("__DATA29") then
      Init_insertautosupply_buylist(80541, true, oldItemTable)
    end
  end
end

function CreateAutoSupplyWnd(dwMainWndHD)
  OnCreateAutoSupplyWnd(dwMainWndHD)
  return 1
end

function OnCreateAutoSupplyWnd(dwMainWndHD)
  local w = window.find(WND_AUTOSUPPLY, 10070)
  game.assistclearmagicitem(w)
  InitAutoSupplyWnd(WND_AUTOSUPPLY)
  ENABLE_SUPPLYPROCESS = 1
  return 1
end

function InitAutoSupplyWnd(dwMainWndHD)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBACK_NOHPITEM, 10063, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBACK_NOMPITEM, 10064, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBACK_BROKENEQ, 10065, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBACK_NOBULLET, 10066, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBACK_NOSPACE, 10067, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISREPAIR, 10072, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISRECALLFIGHT, 10073, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISBUYITEM, 10075, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISDISCARD, 10080, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISDEPOSITGOLDITEM, 10056, true)
  LoadAutoSupplyCheckButton(dwMainWndHD, AS_BOL_ISDEPOSITGOODITEM, 10057, true)
  LoadAutoSupplyEditField(dwMainWndHD, AS_INT_CARRYBOUND, 10055, 800)
  LoadAutoSupplyEditField(dwMainWndHD, AS_INT_SPACEBOUND, 10068, 0)
  LoadAutoSupplyEditField(dwMainWndHD, AS_INT_WAITINGTIME, 10094, 60)
  Init_autosupplyreloadtobuylist()
  game.autosupplyreloadtobuy()
  game.autosupplyreloadtodiscard()
  game.autosupplyloadbackitem()
  return 1
end

function LoadAutoSupplyCheckButton(dwMainWndHD, dataid, windowID, bInit)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local bIsCheck = game.getrobotvar_bool(dataid)
  if bInit == false then
    bIsCheck = true
  end
  window.setcheck(dwSelectedWndHD, bIsCheck)
  return 1
end

function LoadAutoSupplyEditField(dwMainWndHD, dataid, windowID, defaultvalue)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local nLowBoundValue = game.getrobotvar_int(dataid)
  if nLowBoundValue == 0 then
    window.settitle(dwSelectedWndHD, defaultvalue)
    game.setrobotvar_int(dataid, defaultvalue)
  else
    window.settitle(dwSelectedWndHD, nLowBoundValue)
  end
  return 1
end

function LoadAutoSupplyIcon(dwMainWndHD, dataid, windowID, defaultvalue)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local nLowBoundValue = game.getrobotvar_int(dataid)
  if nLowBoundValue == 0 then
    window.settitle(dwSelectedWndHD, defaultvalue)
    game.setrobotvar_int(dataid, defaultvalue)
  else
    window.settitle(dwSelectedWndHD, nLowBoundValue)
  end
  return 1
end

function OnCheckAutoSupplyButton(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  if 1500 <= dataid and dataid < 2000 then
    game.setrobotvar_bool(dataid, window.ischeck(dwID))
    if window.ischeck(dwID) == true then
      window.trace("savecheck true-" .. dwID)
    else
      window.trace("savecheck false-" .. dwID)
    end
  end
  return 1
end

function OnEditAutoSupplyField(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  local nLowBoundValue = tonumber(window.gettitle(dwID))
  if nLowBoundValue == nil then
    nLowBoundValue = 0
  elseif nLowBoundValue < 0 then
    nLowBoundValue = 0
  end
  if 1500 <= dataid and dataid < 2000 then
    game.setrobotvar_int(dataid, nLowBoundValue)
    window.trace("saveint" .. dwID .. ":" .. nLowBoundValue)
  end
  return 1
end

function OnRClickAutoSupplyBackItem(dwID, dwCmdID, dwParam, pParam)
  game.clearbackitem(dwID, AS_INT_BACKTOWNITEM)
  return 1
end

function OnDropAutoSupplyBackItem(dwID, dwCmdID, dwParam, pParam)
  local bIsDroped, nType, nValue = game.dropbackitem(dwID, AS_INT_BACKTOWNITEM, pParam)
  if bIsDroped == false then
    return 0
  end
  window.setappdatafordualint(dwID, nType, nValue)
  return 1
end

function OnPressDepositButton(dwID, dwCmdID, dwParam, pParam)
  game.autosupplyhandleitem(HANDLETYPE_DEPOSIT)
  game.autosupplyreloadtodiscard()
  return 1
end

function OnPressDiscardButton(dwID, dwCmdID, dwParam, pParam)
  game.autosupplyhandleitem(HANDLETYPE_DISCARD)
  game.autosupplyreloadtodiscard()
  return 1
end

function OnPressSaleButton(dwID, dwCmdID, dwParam, pParam)
  game.autosupplyhandleitem(HANDLETYPE_SALE)
  game.autosupplyreloadtodiscard()
  return 1
end

function OnPressRemoveButton(dwID, dwCmdID, dwParam, pParam)
  game.autosupplyhandleitem(HANDLETYPE_REMOVE)
  game.autosupplyreloadtodiscard()
  return 1
end

function OnPressAddCustomItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("AddCustomItem")
  game.autosupplyaddcustom()
  game.autosupplyreloadtodiscard()
  return 1
end

function OnPressBackpackButton(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_AUTOSUPPLYMINIPACK) == false then
    CreateMiniPackDlg()
  end
  return 1
end

function OnEditItemsNum(dwID, dwCmdID, dwParam, pParam)
  local num = window.gettitleint(dwID)
  if num < MAX_SHOOPINGNUM then
    game.autosupplychangeitemnum(num)
  else
    game.autosupplychangeitemnum(MAX_SHOOPINGNUM)
  end
  window.settitle(dwID, 0)
  game.autosupplyreloadtobuy()
  return 1
end

function OnPressaAddItemFromBackpack(dwID, dwCmdID, dwParam, pParam)
  game.addpackitemtohandlelist()
  game.autosupplyreloadtodiscard()
  window.destroy(WND_AUTOSUPPLYMINIPACK)
  return 1
end

function CreateMiniPackDlg()
  WND_AUTOSUPPLYMINIPACK = window.create(10095, 0, 0, SYSTEM_HANDLER)
  game.autoloadpackitemtolist()
  return 1
end
