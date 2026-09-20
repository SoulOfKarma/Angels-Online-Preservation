ICON_ATTRIB_DARK = 1
WND_HOUSEINFO = 0
WND_HOUSEINFO_X = -1
WND_HOUSEINFO_Y = -1
WND_HOUSEPASSWORD = 0
WND_FURNITURELIST = 0
WND_FURNITURELIST_X = -1
WND_FURNITURELIST_Y = -1
WND_FURNITUREINFO = 0
WND_FURNITUREINFO_X = -1
WND_FURNITUREINFO_Y = -1
WND_HOUSEPET_SLOT = 0
WND_HOUSEPET_SLOT_X = -1
WND_HOUSEPET_SLOT_Y = -1
WND_HOUSEMOBGEN_SLOT = 0
WND_HOUSEMOBGEN_SLOT_X = -1
WND_HOUSEMOBGEN_SLOT_Y = -1
WND_FURNITURE_RECYCLE = 0
WND_FURNITURE_RECYCLE_X = -1
WND_FURNITURE_RECYCLE_Y = -1
WND_CASTVOTE_NOTE = 0
WND_CASTVOTE_NOTE_X = -1
WND_CASTVOTE_NOTE_Y = -1
WND_VOTENOTE_LIST = 0
WND_VOTENOTE_LIST_X = -1
WND_VOTENOTE_LIST_Y = -1
WND_HOUSE_STATE = 0
WND_HOUSE_STATE_X = -1
WND_HOUSE_STATE_Y = -1
WND_HITPARADE_HOUSE = 0
WND_HITPARADE_HOUSE_X = -1
WND_HITPARADE_HOUSE_Y = -1
WND_HITPARADE_HOUSE_TYPE = 0
WND_HITPARADE_HOUSE_PAGE = 0
WND_BILLBOARD_HOUSE_TYPE = 0
WND_HITPARADE_HOUSE_SCORE_PAGE = 0

function OnClickCreateHouseInfoWnd(dwID, dwCmdID, dwParam, pParam)
  CreateHouseInfoWnd()
  return 1
end

function CreateHouseInfoWnd()
  if window.isexist(WND_HOUSEINFO) then
    if window.isvisible(WND_HOUSEINFO) then
      window.show(WND_HOUSEINFO, false)
    else
      window.show(WND_HOUSEINFO, true)
      window.setforeground(WND_HOUSEINFO)
    end
    return
  end
  WND_HOUSEINFO = window.create(27001, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_HOUSEINFO_X or 0 > WND_HOUSEINFO_Y then
    window.move(WND_HOUSEINFO, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_HOUSEINFO, WND_HOUSEINFO_X, WND_HOUSEINFO_Y)
  end
  window.regsetting(WND_HOUSEINFO, "WND_HOUSEINFO")
  game.inititemwnd(WND_HOUSEINFO, 5)
  game.updatehouseinfo()
end

function CloseHouseInfoWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_HOUSEINFO)
  WND_HOUSEINFO = 0
  return 1
end

function OnDragFurnitureBagItem(dwID, dwCmdID, dwParam, pParam)
  if game.isfurnitureuse(dwID) then
    return 1
  end
  game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnDropFurnitureBagItem(dwID, dwCmdID, dwParam, pParam)
  if game.isfurnitureuse(dwID) then
    return 1
  end
  if game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function OnRegistryHouse(dwID, dwCmdID, dwParam, pParam)
  local dwCheckPW = window.find(WND_HOUSEINFO, 12979)
  game.registryhouse(dwCheckPW, "")
  return 1
end

function OnFurnishHouse(dwID, dwCmdID, dwParam, pParam)
  game.furnishhouse()
  return 1
end

function OnHouseState(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_HOUSE_STATE) then
    return
  end
  WND_HOUSE_STATE = window.create(27319, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_HOUSE_STATE_X or 0 > WND_HOUSE_STATE_Y then
    window.move(WND_HOUSE_STATE, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_HOUSE_STATE, WND_HOUSE_STATE_X, WND_HOUSE_STATE_Y)
  end
  window.regsetting(WND_HOUSE_STATE, "WND_HOUSE_STATE")
  window.settitle(window.find(WND_HOUSE_STATE, 27320), game.getstring(2516) .. game.getstring(2517) .. game.getstring(2518) .. game.getstring(2519) .. game.getstring(2520) .. game.getstring(2521))
  return 1
end

function OnCloseHouseState(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_HOUSE_STATE)
  WND_HOUSE_STATE = 0
  return 1
end

function OnCloseHouse(dwID, dwCmdID, dwParam, pParam)
  game.closehouse()
  return 1
end

function OnLeaveHouse(dwID, dwCmdID, dwParam, pParam)
  game.leavehouse()
  return 1
end

function OnCreateLeaveFurnishWnd(dwID, dwCmdID, dwParam, pParam)
  local parent = window.parent(dwID)
  local w = window.create(27093, 0, 0, 0)
  window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  return 1
end

function OnLeaveFurnish_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnLeaveFurnish(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  window.destroy(WND_FURNITURELIST)
  window.destroy(WND_FURNITUREINFO)
  WND_FURNITURELIST = 0
  WND_FURNITUREINFO = 0
  game.leavefurnish()
  return 1
end

function OnMoveFurniture(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.movefurniture()
  return 1
end

function OnRotateFurniture(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.rotatefurniture()
  return 1
end

function OnHideFurniture(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.hidefurniture()
  return 1
end

function OnCreateSaveFurnitureWnd(dwID, dwCmdID, dwParam, pParam)
  local parent = window.parent(dwID)
  local w = window.create(27050, 0, 0, 0)
  window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  return 1
end

function OnSaveFurniture_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnSaveFurniture(dwID, dwCmdID, dwParam, pParam)
  game.savefurniture()
  window.destroy(window.parent(dwID))
  return 1
end

function OnClearFurniture(dwID, dwCmdID, dwParam, pParam)
  game.clearfurniture()
  return 1
end

function OnRecoverFurniture(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.recoverfurniture()
  return 1
end

function OnShowAllFurniture(dwID, dwCmdID, dwParam, pParam)
  game.showallfurniture()
  return 1
end

function OnFurnitureMenu(nHide)
  w = window.create(27036, 0, 0, SYSTEM_HANDLER)
  if nHide == 1 then
    window.show(window.find(w, 27039), false)
    window.moveoffset(window.find(w, 27040), 0, -16)
    window.moveoffset(window.find(w, 27041), 0, -16)
    window.setwindowsize(w, window.width(w), window.height(w) - 16)
  end
  t = window.find(w, 27037)
  window.settitle(t, game.getfurniturename())
  local x, y = window.getcursorpos()
  window.limitmove(w, x, y)
end

function OnCheckHouseOption(dwID, dwCmdID, dwParam, pParam)
  game.checkhouseoption(dwID, dwParam)
  return 1
end

function UseHousePassword()
  if window.isexist(WND_HOUSEPASSWORD) then
    return
  end
  WND_HOUSEPASSWORD = window.create(12990, 0, 0, SYSTEM_HANDLER)
  window.move(WND_HOUSEPASSWORD, SYSTEM_SCREEN_WIDTH / 2 - 100, SYSTEM_SCREEN_HEIGHT / 2 - 70)
  return 1
end

function OnSetHousePasswordOK(dwID, dwCmdID, dwParam, pParam)
  wnd = window.find(window.parent(dwID), 12993)
  if window.gettitle(wnd) ~= "" then
    rr = game.sethousepassword(wnd)
    if rr == 0 then
      game.registryhouse(0, window.gettitle(wnd))
      window.destroy(window.parent(dwID))
    else
      game.addsystemmessage(rr)
    end
  else
    game.addsystemmessage(2352)
  end
  return 1
end

function OnSetHousePasswordCancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function CreateFurnitureWindow()
  if window.isexist(WND_FURNITURELIST) == false then
    WND_FURNITURELIST = window.create(27054, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_FURNITURELIST_X or 0 > WND_FURNITURELIST_Y then
      window.move(WND_FURNITURELIST, SYSTEM_SCREEN_WIDTH - window.width(WND_FURNITURELIST), 200)
    else
      window.move(WND_FURNITURELIST, WND_FURNITURELIST_X, WND_FURNITURELIST_Y)
    end
    window.regsetting(WND_FURNITURELIST, "WND_FURNITURELIST")
  end
  if window.isexist(WND_FURNITUREINFO) == false then
    WND_FURNITUREINFO = window.create(27075, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_FURNITUREINFO_X or 0 > WND_FURNITUREINFO_Y then
      window.move(WND_FURNITUREINFO, SYSTEM_SCREEN_WIDTH - window.width(WND_FURNITUREINFO), 0)
    else
      window.move(WND_FURNITUREINFO, WND_FURNITUREINFO_X, WND_FURNITUREINFO_Y)
    end
    window.regsetting(WND_FURNITUREINFO, "WND_FURNITUREINFO")
  end
  window.destroy(WND_HOUSEINFO)
  WND_HOUSEINFO = 0
end

function OnCreateFurnitureTypeList(dwID, dwCmdID, dwParam, pParam)
  game.insertfurnituretype(window.create(27059, window.parent(dwID), 0, SYSTEM_HANDLER))
  return 1
end

function OnSelectFurnitureType(dwID, dwCmdID, dwParam, pParam)
  game.updatefurniturelist(dwID)
  window.destroy(window.parent(dwID))
  return 1
end

function OnUseFurniture(dwID, dwCmdID, dwParam, pParam)
  game.usefurniture(dwID, dwParam)
  return 1
end

WND_CLICK_HOUSEOBJ_ID = 0

function OnHouseObjMenu()
  if WND_CLICK_HOUSEOBJ_ID == 0 then
    return 0
  end
  w = window.create(12970, 0, 0, SYSTEM_HANDLER)
  t = window.find(w, 12971)
  window.settitle(t, game.gethousename(WND_CLICK_HOUSEOBJ_ID))
  local x, y = window.getcursorpos()
  window.limitmove(w, x, y)
  return 1
end

function OnClickHouseEnterHouse(dwID, dwCmdID, dwParam, pParam)
  if WND_CLICK_HOUSEOBJ_ID == 0 then
    return 0
  end
  window.destroy(window.parent(dwID))
  game.tryentryhouse(WND_CLICK_HOUSEOBJ_ID)
  return 1
end

function OnClickHouseShowInfo(dwID, dwCmdID, dwParam, pParam)
  if WND_CLICK_HOUSEOBJ_ID == 0 then
    return 0
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnOpenHousePWWnd(dwHouseObjID)
  if WND_CLICK_HOUSEOBJ_ID ~= dwHouseObjID then
    return 0
  end
  local wHouseMenuHD = window.find(0, 12970)
  window.destroy(wHouseMenuHD)
  wPWHD = window.create(12980, 0, 0, SYSTEM_HANDLER)
  t = window.find(wPWHD, 12981)
  window.settitle(t, game.gethousename(WND_CLICK_HOUSEOBJ_ID) .. game.getstring(2367))
  window.move(wPWHD, SYSTEM_SCREEN_WIDTH / 2 - 80, SYSTEM_SCREEN_HEIGHT / 2 - 50)
  return 1
end

function OnTryPWEnterHouse(dwID, dwCmdID, dwParam, pParam)
  local dwPWWndHD = window.parent(dwID)
  local pw = window.find(dwPWWndHD, 12982)
  game.trypwenterhouse(WND_CLICK_HOUSEOBJ_ID, window.gettitle(pw))
  WND_CLICK_HOUSEOBJ_ID = 0
  window.destroy(dwPWWndHD)
  return 1
end

function OnCancelEntryHousePW(dwID, dwCmdID, dwParam, pParam)
  WND_CLICK_HOUSEOBJ_ID = 0
  window.destroy(window.parent(dwID))
  return 1
end

WND_ICON_INVAILD_ITEM = 27201
WND_HOUSEPET_ITEM_RES_ID = 27210
WND_HOUSEPET_SLOT_RES_ID = 27220
WND_HOUSEPET_RADIO_RES_ID = 27261

function CreateHousePetSlotWindow()
  if window.isexist(WND_HOUSEPET_SLOT) == false then
    WND_HOUSEPET_SLOT = window.create(27202, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_HOUSEPET_SLOT_X or 0 > WND_HOUSEPET_SLOT_Y then
      window.move(WND_HOUSEPET_SLOT, SYSTEM_SCREEN_WIDTH / 2 - 110, SYSTEM_SCREEN_HEIGHT / 2 - 80)
    else
      window.move(WND_HOUSEPET_SLOT, WND_HOUSEPET_SLOT_X, WND_HOUSEPET_SLOT_Y)
    end
    window.regsetting(WND_HOUSEPET_SLOT, "WND_HOUSEPET_SLOT")
  end
  game.inititemwnd(WND_HOUSEPET_SLOT, 6)
  UpdateHousePetSlotWindow()
  return 1
end

function UpdateHousePetSlotWindow()
  if WND_HOUSEPET_SLOT == 0 or window.isexist(WND_HOUSEPET_SLOT) == false then
    return 0
  end
  local nVaildNum = game.gethousepetvaildnum()
  local nMaxNum = game.gethousepetmaxnum()
  local dwSlotWndID
  for i = 1, nVaildNum do
    dwSlotWndID = window.find(WND_HOUSEPET_SLOT, WND_HOUSEPET_SLOT_RES_ID + (i - 1))
    window.seticon(dwSlotWndID, 0)
    UpdateHousePetRadioButton(WND_HOUSEPET_SLOT, WND_HOUSEPET_RADIO_RES_ID + (i - 1) * 3, i, false)
    window.trace("UpdateHousePetSlotWindow() vaild : " .. i)
  end
  for i = nVaildNum + 1, nMaxNum do
    dwSlotWndID = window.find(WND_HOUSEPET_SLOT, WND_HOUSEPET_SLOT_RES_ID + (i - 1))
    window.seticon(dwSlotWndID, WND_ICON_INVAILD_ITEM)
    UpdateHousePetRadioButton(WND_HOUSEPET_SLOT, WND_HOUSEPET_RADIO_RES_ID + (i - 1) * 3, i, true)
    window.trace("UpdateHousePetSlotWindow() invaild : " .. i)
  end
  return 1
end

function UpdateHousePetRadioButton(dwMainWndHD, dwWindowID, nAppData, bDisable)
  local dwRadioWnd = window.find(dwMainWndHD, dwWindowID)
  local dwRadioWnd2 = window.find(dwMainWndHD, dwWindowID + 1)
  local dwRadioWnd3 = window.find(dwMainWndHD, dwWindowID + 2)
  local nRadio = game.gethousepetradio(nAppData)
  if 0 <= nRadio and nRadio <= 2 then
    window.setradio(dwRadioWnd, nRadio)
  end
  if bDisable == true then
    window.enable(dwRadioWnd, false)
    window.enable(dwRadioWnd2, false)
    window.enable(dwRadioWnd3, false)
  else
    window.enable(dwRadioWnd, true)
    window.enable(dwRadioWnd2, true)
    window.enable(dwRadioWnd3, true)
  end
  return 1
end

function OnHousePetRadio(dwID, dwCmdID, dwParam, pParam)
  local nAppData = window.getappdata(dwID)
  local nRadio = window.getradio(dwID)
  window.trace("OnHousePetRadio() appdata:" .. nAppData .. ",radio:" .. nRadio)
  if 1 <= nAppData and nAppData <= 10 then
    game.sethousepetradio(nAppData, nRadio)
  end
  return 1
end

function OnDragHousePetSlotItem(dwID, dwCmdID, dwParam, pParam)
  if game.atselfhouse(dwID) then
    game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  end
  return 1
end

function OnDropHousePetSlotItem(dwID, dwCmdID, dwParam, pParam)
  if game.atselfhouse(dwID) and game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function CloseHousePetWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_HOUSEPET_SLOT)
  WND_HOUSEPET_SLOT = 0
  return 1
end

WND_HOUSEMOBGEN_ITEM_RES_ID = 27240
WND_HOUSEMOBGEN_SLOT_RES_ID = 27250

function CreateHouseMobGenSlotWindow()
  if window.isexist(WND_HOUSEMOBGEN_SLOT) == false then
    WND_HOUSEMOBGEN_SLOT = window.create(27232, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_HOUSEMOBGEN_SLOT_X or 0 > WND_HOUSEMOBGEN_SLOT_Y then
      window.move(WND_HOUSEMOBGEN_SLOT, SYSTEM_SCREEN_WIDTH / 2 - 110, SYSTEM_SCREEN_HEIGHT / 2 - 80)
    else
      window.move(WND_HOUSEMOBGEN_SLOT, WND_HOUSEMOBGEN_SLOT_X, WND_HOUSEMOBGEN_SLOT_Y)
    end
    window.regsetting(WND_HOUSEMOBGEN_SLOT, "WND_HOUSEMOBGEN_SLOT")
  end
  game.inititemwnd(WND_HOUSEMOBGEN_SLOT, 7)
  UpdateHouseMobGenSlotWindow()
  return 1
end

function UpdateHouseMobGenSlotWindow()
  if WND_HOUSEMOBGEN_SLOT == 0 or window.isexist(WND_HOUSEMOBGEN_SLOT) == false then
    return 0
  end
  local nVaildNum = game.gethousemobgenvaildnum()
  local nMaxNum = game.gethousemobgenmaxnum()
  local dwSlotWndID
  for i = 1, nVaildNum do
    dwSlotWndID = window.find(WND_HOUSEMOBGEN_SLOT, WND_HOUSEMOBGEN_SLOT_RES_ID + (i - 1))
    window.seticon(dwSlotWndID, 0)
    window.trace("UpdateHousePetSlotWindow() vaild : " .. i)
  end
  for i = nVaildNum + 1, nMaxNum do
    dwSlotWndID = window.find(WND_HOUSEMOBGEN_SLOT, WND_HOUSEMOBGEN_SLOT_RES_ID + (i - 1))
    window.seticon(dwSlotWndID, WND_ICON_INVAILD_ITEM)
    window.trace("UpdateHousePetSlotWindow() invaild : " .. i)
  end
  return 1
end

function OnDragHouseMobGenSlotItem(dwID, dwCmdID, dwParam, pParam)
  if game.atselfhouse(dwID) then
    game.dragcharitem(dwID, dwCmdID, dwParam, pParam)
  end
  return 1
end

function OnDropHouseMobGenSlotItem(dwID, dwCmdID, dwParam, pParam)
  if game.atselfhouse(dwID) and game.dropcharitem(dwID, dwCmdID, dwParam, pParam) then
    return 1
  end
  return 0
end

function CloseHouseMobGenWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_HOUSEMOBGEN_SLOT)
  WND_HOUSEMOBGEN_SLOT = 0
  return 1
end

function CreateFurnitureRecycleWnd()
  if window.isexist(WND_FURNITURE_RECYCLE) then
    return 1
  end
  WND_FURNITURE_RECYCLE = window.create(27301, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_FURNITURE_RECYCLE_X or 0 > WND_FURNITURE_RECYCLE_Y then
    window.move(WND_FURNITURE_RECYCLE, SYSTEM_SCREEN_WIDTH / 2 - 110, SYSTEM_SCREEN_HEIGHT / 2 - 80)
  else
    window.move(WND_FURNITURE_RECYCLE, WND_FURNITURE_RECYCLE_X, WND_FURNITURE_RECYCLE_Y)
  end
  window.regsetting(WND_FURNITURE_RECYCLE, "WND_FURNITURE_RECYCLE")
  game.inititemwnd(WND_FURNITURE_RECYCLE, 8)
end

function OnDropFurnitureRecycle(dwID, dwCmdID, dwParam, pParam)
  game.dropfurniturerecycle(dwID, pParam)
  return 1
end

function OnCloseFurnitureRecycle(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_FURNITURE_RECYCLE)
  WND_FURNITURE_RECYCLE = 0
  return 1
end

function OnFurnitureRecycle(dwID, dwCmdID, dwParam, pParam)
  game.furniturerecycle(WND_FURNITURE_RECYCLE)
  return 1
end

function OnClearFurnitureRecycle(dwID, dwCmdID, dwParam, pParam)
  game.clearfurniturerecycle(WND_FURNITURE_RECYCLE)
  return 1
end

function CreateHouseCastVoteNoteWindow(szOwnerName)
  if window.isexist(WND_CASTVOTE_NOTE) == false then
    WND_CASTVOTE_NOTE = window.create(27401, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_CASTVOTE_NOTE_X or 0 > WND_CASTVOTE_NOTE_Y then
      window.move(WND_CASTVOTE_NOTE, SYSTEM_SCREEN_WIDTH / 2 - 143, SYSTEM_SCREEN_HEIGHT / 2 - 125)
    else
      window.move(WND_CASTVOTE_NOTE, WND_CASTVOTE_NOTE_X, WND_CASTVOTE_NOTE_Y)
    end
    window.regsetting(WND_CASTVOTE_NOTE, "WND_CASTVOTE_NOTE")
  end
  local wToNameWnd = window.find(WND_CASTVOTE_NOTE, 27403)
  window.settitle(wToNameWnd, szOwnerName)
  return 1
end

function OnCloseCastVoteWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_CASTVOTE_NOTE)
  WND_CASTVOTE_NOTE = 0
  return 1
end

function OnHouseCastVote(dwID, dwCmdID, dwParam, pParam)
  local wNoteWnd = window.find(WND_CASTVOTE_NOTE, 27404)
  local szNote = window.gettitle(wNoteWnd)
  game.trycastvote(szNote)
  window.destroy(WND_CASTVOTE_NOTE)
  WND_CASTVOTE_NOTE = 0
  return 1
end

function CreateHouseViewVoteNoteWnd()
  if window.isexist(WND_VOTENOTE_LIST) == false then
    WND_VOTENOTE_LIST = window.create(27411, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_VOTENOTE_LIST_X or 0 > WND_VOTENOTE_LIST_Y then
      window.move(WND_VOTENOTE_LIST, SYSTEM_SCREEN_WIDTH / 2 - 110, SYSTEM_SCREEN_HEIGHT / 2 - 80)
    else
      window.move(WND_VOTENOTE_LIST, WND_VOTENOTE_LIST_X, WND_VOTENOTE_LIST_Y)
    end
    window.regsetting(WND_VOTENOTE_LIST, "WND_VOTENOTE_LIST")
  end
  game.updatevotenotelist(WND_VOTENOTE_LIST)
  return 1
end

function OnSelectVoteNoteList(dwID, dwCmdID, dwParam, pParam)
  local parentid = window.parent(dwID)
  game.selectvotenotelist(parentid)
  return 1
end

function OnTryGoToSenderHouse(dwID, dwCmdID, dwParam, pParam)
  local parentid = window.parent(dwID)
  game.trygotosenderhouse(parentid)
  return 1
end

function OnChangeVoteNoteListPage(dwID, dwCmdID, dwParam, pParam)
  local nAppData = window.getappdata(dwID)
  game.votenotechangepage(nAppData, false)
  return 1
end

function OnChangeVoteNoteListPageEx(dwID, dwCmdID, dwParam, pParam)
  local nAppData = window.getappdata(dwID)
  game.votenotechangepage(nAppData, true)
  return 1
end

function OnCloseVoteNoteWnd(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_VOTENOTE_LIST)
  WND_VOTENOTE_LIST = 0
  return 1
end

function CreateListHousePWWnd(dwDestOwnerID)
  if WND_VOTENOTE_LIST == 0 then
    return 0
  end
  wPWHD = window.create(27441, 0, 0, SYSTEM_HANDLER)
  window.setappdata(wPWHD, dwDestOwnerID)
  window.move(wPWHD, SYSTEM_SCREEN_WIDTH / 2 - 75, SYSTEM_SCREEN_HEIGHT / 2 - 40)
  return 1
end

function OnListTryPWEnterHouse(dwID, dwCmdID, dwParam, pParam)
  local dwPWWndHD = window.parent(dwID)
  local pw = window.find(dwPWWndHD, 27443)
  game.listtrypwenterhouse(window.getappdata(dwPWWndHD), window.gettitle(pw))
  window.destroy(dwPWWndHD)
  return 1
end

function OnListCancelEntryHousePW(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function CreateHitParadeHouse()
  if window.isexist(WND_HITPARADE_HOUSE) then
    return
  end
  WND_HITPARADE_HOUSE = window.create(27601, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_HITPARADE_HOUSE_X or 0 > WND_HITPARADE_HOUSE_Y then
    window.move(WND_HITPARADE_HOUSE, SYSTEM_SCREEN_WIDTH / 2 - 110, SYSTEM_SCREEN_HEIGHT / 2 - 80)
  else
    window.move(WND_HITPARADE_HOUSE, WND_HITPARADE_HOUSE_X, WND_HITPARADE_HOUSE_Y)
  end
  window.regsetting(WND_HITPARADE_HOUSE, "WND_HITPARADE_HOUSE")
  window.setcheck(window.find(WND_HITPARADE_HOUSE, 27604), true)
  window.setcheck(window.find(WND_HITPARADE_HOUSE, 27606), true)
  window.setcheck(window.find(WND_HITPARADE_HOUSE, 27616), true)
  window.settitle(WND_HITPARADE_HOUSE, window.gettitle(window.find(WND_HITPARADE_HOUSE, 27604)))
  WND_HITPARADE_HOUSE_TYPE = 33
  WND_HITPARADE_HOUSE_PAGE = 0
  WND_BILLBOARD_HOUSE_TYPE = 0
end

function OnHitParadeHouseChangeType(dwID, dwCmdID, dwParam, pParam)
  WND_HITPARADE_HOUSE_TYPE = window.getappdata(dwID)
  WND_HITPARADE_HOUSE_PAGE = 0
  game.netcommand2(41, WND_HITPARADE_HOUSE_TYPE, WND_HITPARADE_HOUSE_PAGE)
  game.showhitparadehousedata()
  return 1
end

function OnHitParadeHouseChangePage(dwID, dwCmdID, dwParam, pParam)
  local nPage = window.getappdata(window.find(WND_HITPARADE_HOUSE, 27614))
  local nAppData = window.getappdata(dwID)
  if nAppData == 1 then
    nPage = nPage + 1
  elseif nAppData == 0 then
    nPage = nPage - 1
  end
  if nPage < 0 then
    nPage = 0
  elseif 4 < nPage then
    nPage = 4
  end
  WND_HITPARADE_HOUSE_PAGE = nPage
  game.netcommand2(41, WND_HITPARADE_HOUSE_TYPE, WND_HITPARADE_HOUSE_PAGE)
  game.showhitparadehousedata()
  return 1
end

function OnHitParadeHouseChangeShow(dwID, dwCmdID, dwParam, pParam)
  window.settitle(WND_HITPARADE_HOUSE, window.gettitle(dwID))
  local nAppData = window.getappdata(dwID)
  if nAppData == 0 then
    window.show(window.find(WND_HITPARADE_HOUSE, 27602), true)
    window.show(window.find(WND_HITPARADE_HOUSE, 27603), false)
    window.show(window.find(WND_HITPARADE_HOUSE, 27629), false)
    WND_HITPARADE_HOUSE_TYPE = 33
    WND_HITPARADE_HOUSE_PAGE = 0
    window.setcheck(window.find(WND_HITPARADE_HOUSE, 27606), true)
    window.setcheck(window.find(WND_HITPARADE_HOUSE, 27607), false)
    window.setcheck(window.find(WND_HITPARADE_HOUSE, 27608), false)
    game.showhitparadehousedata()
    game.netcommand2(41, WND_HITPARADE_HOUSE_TYPE, WND_HITPARADE_HOUSE_PAGE)
  elseif nAppData == 1 then
    window.show(window.find(WND_HITPARADE_HOUSE, 27603), true)
    window.show(window.find(WND_HITPARADE_HOUSE, 27602), false)
    window.show(window.find(WND_HITPARADE_HOUSE, 27629), false)
    WND_BILLBOARD_HOUSE_TYPE = 0
    window.setcheck(window.find(WND_HITPARADE_HOUSE, 27616), true)
    window.setcheck(window.find(WND_HITPARADE_HOUSE, 27617), false)
    game.showbillboardhousedata()
    game.netcommand2(42, WND_BILLBOARD_HOUSE_TYPE, 0)
  elseif nAppData == 2 then
    window.show(window.find(WND_HITPARADE_HOUSE, 27602), false)
    window.show(window.find(WND_HITPARADE_HOUSE, 27603), false)
    window.show(window.find(WND_HITPARADE_HOUSE, 27629), true)
    WND_HITPARADE_HOUSE_SCORE_PAGE = 0
    game.showhitparadehousescore()
    game.netcommand2(41, 34, WND_HITPARADE_HOUSE_PAGE)
  end
  return 1
end

function OnBillBoardHouseChangeType(dwID, dwCmdID, dwParam, pParam)
  WND_BILLBOARD_HOUSE_TYPE = window.getappdata(dwID)
  game.netcommand2(42, WND_BILLBOARD_HOUSE_TYPE, 0)
  game.showbillboardhousedata()
  return 1
end

function OnGotoBillBoardHouse(dwID, dwCmdID, dwParam, pParam)
  game.gotobillboardhouse()
  return 1
end

function OnCloseHitParadeHouse(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_HITPARADE_HOUSE)
  WND_HITPARADE_HOUSE = 0
  return 1
end

function OnHitParadeHouseScoreChangePage(dwID, dwCmdID, dwParam, pParam)
  local nPage = window.getappdata(window.find(WND_HITPARADE_HOUSE, 27637))
  local nAppData = window.getappdata(dwID)
  if nAppData == 1 then
    nPage = nPage + 1
  elseif nAppData == 0 then
    nPage = nPage - 1
  end
  if nPage < 0 then
    nPage = 0
  elseif 4 < nPage then
    nPage = 4
  end
  WND_HITPARADE_HOUSE_SCORE_PAGE = nPage
  game.netcommand2(41, 34, WND_HITPARADE_HOUSE_SCORE_PAGE)
  game.showhitparadehousescore()
  return 1
end
