EQUIP_WEAPON_SET = 0
WND_EQUIP_VIEW = 0
WND_EQUIP_PET_NEW = 0
WND_EQUIP_PET_NEW_ATTRIB_CHECK = 0
WND_EQUIP_PET_NEW_VALUE_CHECK = 0
WND_EQUIP_PET_NEW_ALL_CHECK = 0
WND_EQUIP_PET_NEW_CHECK_ITEMUSE = 0
WND_EQUIP_PET_NEW_LIST = 0
n_Page = 1
n_openedSlotClount = -1
EQUIP_PET_NEW_SLOT_1_ID = 559
EQUIP_PET_NEW_BTN_ID = 18101
EQUIP_PET_NEW_CANNOT_ID = 18151
EQUIP_PET_NEW_SLOT_NUM = 40
EQUIP_PET_A_PAGE_COUNT = 4
IS_SHOW_CHECK_ITEM = 0
IS_CLICK_SURE = 0
SHOW_EQUIPPETNEW_PAGE = 1
MAX_EQUIPPETNEW_PAGE = 8
Temp_DwID = 0
ParamBoth = 1
ParamAttrib = 2
ParamPercent = 3
WND_SKIN_SLOT = 0

function CreateEquipPetNewWnd()
  if window.isexist(WND_EQUIP_PET_NEW) then
    window.destroy(WND_EQUIP_PET_NEW)
    WND_EQUIP_PET_NEW = 0
    return
  end
  WND_EQUIP_PET_NEW = window.create(17150, 0, 0, SYSTEM_HANDLER)
  game.inititemwnd(WND_EQUIP_PET_NEW, 9)
  local page = window.find(WND_EQUIP_PET_NEW, 17152)
  OnChangeEquipPetNewPage(page, 0, 0, 0)
  IS_CLICK_SURE = 0
  UpdateEquipPetNew()
  return 1
end

function OnChangeEquipPetNewPage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local btn1 = window.find(WND_EQUIP_PET_NEW, 17152)
  local page1 = window.find(WND_EQUIP_PET_NEW, 17151)
  local btn2 = window.find(WND_EQUIP_PET_NEW, 17154)
  local page2 = window.find(WND_EQUIP_PET_NEW, 17153)
  local btn3 = window.find(WND_EQUIP_PET_NEW, 17156)
  local page3 = window.find(WND_EQUIP_PET_NEW, 17155)
  if appdata == 17152 then
    window.show(page1, true)
    window.show(page2, false)
    window.show(page3, false)
    window.setcheck(btn1, true)
    window.setcheck(btn2, false)
    window.setcheck(btn3, false)
    UpdateEquipPetNewPage1()
  elseif appdata == 17154 then
    game.showAchieveEquipPetNew()
    window.show(page1, false)
    window.show(page2, true)
    window.show(page3, false)
    window.setcheck(btn1, false)
    window.setcheck(btn2, true)
    window.setcheck(btn3, false)
  elseif appdata == 17156 then
    window.show(page1, false)
    window.show(page2, false)
    window.show(page3, true)
    window.setcheck(btn1, false)
    window.setcheck(btn2, false)
    window.setcheck(btn3, true)
    window.show(btn1, true)
    window.show(btn2, true)
    window.show(btn3, true)
    UpdateEquipPetNewPage3()
  end
  return 1
end

function UpdateEquipPetNewPage3()
  local word = window.find(WND_EQUIP_PET_NEW, 17005)
  window.settitle(word, game.getstring(3427))
end

function UpdateEquipPetNew()
  n_openedSlotClount = game.getEquipPetSlot()
  UpdateEquipPetNewPage1()
  game.getEquipPetNeedNumToOpen()
  game.showEquipPetNewPetName()
  return 1
end

function UpdateEquipPetNewPage1()
  ShowEquipPetNewSlot()
  return 1
end

function ClearWndShow()
  for i = 1, EQUIP_PET_NEW_SLOT_NUM do
    local showWin = window.find(WND_EQUIP_PET_NEW, 18100 + i)
    window.show(showWin, false)
    window.enable(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18150 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 17350 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18000 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18200 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18300 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18400 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18500 + i)
    window.show(showWin, false)
    showWin = window.find(WND_EQUIP_PET_NEW, 18250 + i)
    window.show(showWin, false)
  end
  return 1
end

function ShowEquipPetNewSlot()
  ClearWndShow()
  local n_start = (SHOW_EQUIPPETNEW_PAGE - 1) * EQUIP_PET_A_PAGE_COUNT + 1
  local n_end = n_start + EQUIP_PET_A_PAGE_COUNT - 1
  if n_end < n_openedSlotClount then
    for i = n_start, n_end do
      local showWin
      showWin = window.find(WND_EQUIP_PET_NEW, 18000 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18200 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18300 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18400 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18500 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18250 + i)
      window.show(showWin, true)
    end
  elseif n_start > n_openedSlotClount then
    for i = n_start, n_end do
      local showWin = window.find(WND_EQUIP_PET_NEW, 18100 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18150 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 17350 + i)
      window.show(showWin, true)
    end
  else
    for i = n_start, n_openedSlotClount do
      local showWin
      showWin = window.find(WND_EQUIP_PET_NEW, 18000 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18200 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18300 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18400 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18500 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18250 + i)
      window.show(showWin, true)
    end
    for i = n_openedSlotClount + 1, n_end do
      local showWin = window.find(WND_EQUIP_PET_NEW, 18100 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 18150 + i)
      window.show(showWin, true)
      showWin = window.find(WND_EQUIP_PET_NEW, 17350 + i)
      window.show(showWin, true)
    end
  end
  local btn
  btn = window.find(WND_EQUIP_PET_NEW, EQUIP_PET_NEW_BTN_ID + n_openedSlotClount)
  window.enable(btn, true)
  UpdateEquipPetPage1Word()
  local showWin = window.find(WND_EQUIP_PET_NEW, 18603)
  local sA = SHOW_EQUIPPETNEW_PAGE .. "/" .. MAX_EQUIPPETNEW_PAGE
  window.settitle(showWin, sA)
  return 1
end

function OnChangeEquipPetPage(dwID, dwCmdID, dwParam, pParam)
  ClearWndShow()
  if dwCmdID == 17274 and SHOW_EQUIPPETNEW_PAGE > 1 then
    SHOW_EQUIPPETNEW_PAGE = SHOW_EQUIPPETNEW_PAGE - 1
  elseif dwCmdID == 17275 and SHOW_EQUIPPETNEW_PAGE < MAX_EQUIPPETNEW_PAGE then
    SHOW_EQUIPPETNEW_PAGE = SHOW_EQUIPPETNEW_PAGE + 1
  end
  UpdateEquipPetNewPage1()
  return 1
end

function UpdateEquipPetPage1Word()
  local wnd
  local w1 = -1
  local w2 = -1
  local s = game.getstring(3431)
  local sz, sA
  for i = 0, n_openedSlotClount - 1 do
    wnd = window.find(WND_EQUIP_PET_NEW, 18201 + i)
    w1 = game.getEquipPetSlotAttrib(i)
    w2 = game.getEquipPetSlotValue(i)
    if w1 == 1 then
      sz = game.getstring(3259)
    elseif w1 == 3 then
      sz = game.getstring(3260)
    elseif w1 == 8 then
      sz = game.getstring(520)
    elseif w1 == 10 then
      sz = game.getstring(521)
    elseif w1 == 11 then
      sz = game.getstring(522)
    elseif w1 == 12 then
      sz = game.getstring(523)
    elseif w1 == 13 then
      sz = game.getstring(524)
    elseif w1 == 14 then
      sz = game.getstring(525)
    else
      sz = game.getstring(3259)
    end
    sA = s .. sz .. "+" .. w2 .. "%"
    window.settitle(wnd, sA)
  end
  return 1
end

function SendToChangeSlotAttrib(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.isBagHaveItem(ParamAttrib, IS_CLICK_SURE, appdata)
  return 1
end

function SendToChangeSlotValue(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.isBagHaveItem(ParamPercent, IS_CLICK_SURE, appdata)
  return 1
end

function SendToChangeSlotBoth(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.isBagHaveItem(ParamBoth, IS_CLICK_SURE, appdata)
  return 1
end

function ChangeShowItmeUseTipWindow(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    IS_CLICK_SURE = 1
  else
    IS_CLICK_SURE = 0
  end
  UpdateEquipPetNew()
  return 1
end

function CreateEquipPetAttribCheck()
  local Wnd = WND_EQUIP_PET_NEW
  WND_EQUIP_PET_NEW_ATTRIB_CHECK = window.create(17263, Wnd, 0, 0)
  local x, y
  x = window.left(Wnd)
  y = window.top(Wnd)
  window.move(WND_EQUIP_PET_NEW_ATTRIB_CHECK, x, y * 1.15)
  return 1
end

function OnOpenEquipSlot_OK()
  game.sendChangeSlotSetting()
  window.destroy(WND_EQUIP_PET_NEW_ATTRIB_CHECK)
  WND_EQUIP_PET_NEW_ATTRIB_CHECK = 0
  return 1
end

function OnOpenEquipSlot_Cancel()
  window.destroy(WND_EQUIP_PET_NEW_ATTRIB_CHECK)
  WND_EQUIP_PET_NEW_ATTRIB_CHECK = 0
  UpdateEquipPetNew()
  return 1
end

function CreateEquipPetAllCheck()
  WND_EQUIP_PET_NEW_ALL_CHECK = window.create(17289, WND_EQUIP_PET_NEW, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_EQUIP_PET_NEW)
  y = window.top(WND_EQUIP_PET_NEW)
  window.move(WND_EQUIP_PET_NEW_ALL_CHECK, x, y * 1.15)
  return 1
end

function CreateEquipPetAllCheck_OK()
  game.sendChangeSlotSetting()
  window.destroy(WND_EQUIP_PET_NEW_ALL_CHECK)
  WND_EQUIP_PET_NEW_ALL_CHECK = 0
  return 1
end

function CreateEquipPetAllCheck_Cancel()
  window.destroy(WND_EQUIP_PET_NEW_ALL_CHECK)
  WND_EQUIP_PET_NEW_ALL_CHECK = 0
  UpdateEquipPetNew()
  return 1
end

function CreateEquipPetValueCheck()
  WND_EQUIP_PET_NEW_VALUE_CHECK = window.create(17281, WND_EQUIP_PET_NEW, 0, SYSTEM_HANDLER)
  local x, y
  x = window.left(WND_EQUIP_PET_NEW)
  y = window.top(WND_EQUIP_PET_NEW)
  window.move(WND_EQUIP_PET_NEW_VALUE_CHECK, x, y * 1.15)
  return 1
end

function EquipPetValueCheck_OK()
  game.sendChangeSlotSetting()
  window.destroy(WND_EQUIP_PET_NEW_VALUE_CHECK)
  WND_EQUIP_PET_NEW_VALUE_CHECK = 0
  return 1
end

function EquipPetValueCheck_Cancel()
  window.destroy(WND_EQUIP_PET_NEW_VALUE_CHECK)
  WND_EQUIP_PET_NEW_VALUE_CHECK = 0
  UpdateEquipPetNew()
  return 1
end

function OpenUseEquipPetNew()
  if window.isexist(WND_EQUIP_PET_NEW_LIST) then
    window.destroy(WND_EQUIP_PET_NEW_LIST)
    WND_EQUIP_PET_NEW_LIST = 0
    return
  end
  WND_EQUIP_PET_NEW_LIST = window.create(17261, WND_EQUIP_PET_NEW, 0, SYSTEM_HANDLER)
  local x = window.left(WND_EQUIP_PET_NEW)
  local y = window.top(WND_EQUIP_PET_NEW)
  window.move(WND_EQUIP_PET_NEW_LIST, x, y)
  window.setforeground(WND_EQUIP_PET_NEW_LIST)
  game.equipPetItemUpdate()
  return 1
end

function OnSetEquipPetItemValue(dwID, dwCmdID, dwParam, pParam)
  game.setEquipItemValue(window.parent(dwID), true)
  return 1
end

function OnSetEquipPetItemEx(dwID, dwCmdID, dwParam, pParam)
  game.setEquipPetItemEx(window.parent(dwID), dwParam)
  return 1
end

function OnEquipPetUseItemEdit(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, -1)
  game.setEquipItemValue(window.parent(dwID), false)
  return 1
end

function OnEquipPetUseItemScroll(dwID, dwCmdID, dwParam, pParam)
  window.scrolledit(dwID, dwParam)
  game.setEquipItemValue(window.parent(dwID), false)
  return 1
end

function OnSetEquipPet_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_EQUIP_PET_NEW_LIST)
  WND_EQUIP_PET_NEW_LIST = 0
  return 1
end

function OnSetEquipPet_CheckUse(dwID, dwCmdID, dwParam, pParam)
  game.equipPetUseOpenItemCheck(window.parent(dwID))
  return 1
end

function OnEquipPetNewOpen_Confirm(dwID, dwCmdID, dwParam, pParam)
  game.equipPetUseOpenConfirm(window.parent(dwID))
  window.destroy(window.parent(dwID))
  return 1
end

function OnEquipPetNewOpen_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnDropEquipPetNewItem(dwID, dwCmdID, dwParam, pParam)
  game.dropEquipPetItem(dwID)
  return 1
end

function UpdateWeaponSet()
  local bCheck1, bCheck2
  if EQUIP_WEAPON_SET == 0 then
    bCheck1 = true
    bCheck2 = false
  else
    bCheck1 = false
    bCheck2 = true
  end
  window.setcheck(window.find(WND_EQUIP, 2012), bCheck1)
  window.setcheck(window.find(WND_EQUIP, 2014), bCheck1)
  window.setcheck(window.find(WND_EQUIP, 2013), bCheck2)
  window.setcheck(window.find(WND_EQUIP, 2015), bCheck2)
end

function SwitchWeaponSet()
  if EQUIP_WEAPON_SET ~= 0 then
    EQUIP_WEAPON_SET = 0
  else
    EQUIP_WEAPON_SET = 1
  end
  UpdateWeaponSet()
  game.netcommand(13)
end

function OnCheckButtonOne(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    EQUIP_WEAPON_SET = 0
  else
    EQUIP_WEAPON_SET = 1
  end
  UpdateWeaponSet()
  game.netcommand(13)
  return 1
end

function OnCheckButtonTwo(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    EQUIP_WEAPON_SET = 1
  else
    EQUIP_WEAPON_SET = 0
  end
  UpdateWeaponSet()
  game.netcommand(13)
  return 1
end

function CreateEquipWnd()
  if window.isexist(WND_EQUIP) then
    window.destroy(WND_EQUIP)
    WND_EQUIP = 0
    return
  end
  WND_EQUIP = window.create(2001, 0, 0, SYSTEM_HANDLER)
  window.setcheck(window.find(WND_EQUIP, 2004), true)
  if 0 > WND_EQUIP_X or 0 > WND_EQUIP_Y then
    window.move(WND_EQUIP, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_EQUIP, WND_EQUIP_X, WND_EQUIP_Y)
  end
  game.inititemwnd(WND_EQUIP, 2)
  game.inititemwnd(WND_EQUIP, 3)
  game.inititemwnd(WND_EQUIP, 11)
  if game.isdef("__EQUIP_PET_NEW") then
  end
  UpdateWeaponSet()
  window.regsetting(WND_EQUIP, "WND_EQUIP")
  if game.isdef("__ITEM_FUSE") then
    local w = window.find(WND_EQUIP, 2002)
    window.seticon(w, 481)
  end
end

function OnEquipChangePage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  if appdata == 2004 then
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2005), false)
    window.setcheck(window.find(window.parent(dwID), 2006), false)
    window.show(window.find(window.parent(dwID), 2002), true)
    window.show(window.find(window.parent(dwID), 2003), false)
    window.show(window.find(window.parent(dwID), 2007), false)
    if game.isdef("__ITEM_FUSE") then
      local w = window.find(window.parent(dwID), 2002)
      window.seticon(w, 481)
    end
    WND_SKIN_SLOT = 0
  elseif appdata == 2005 then
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2004), false)
    window.setcheck(window.find(window.parent(dwID), 2006), false)
    window.show(window.find(window.parent(dwID), 2002), false)
    window.show(window.find(window.parent(dwID), 2003), true)
    window.show(window.find(window.parent(dwID), 2007), false)
    WND_SKIN_SLOT = 0
  elseif appdata == 2006 then
    window.setcheck(dwID, true)
    window.setcheck(window.find(window.parent(dwID), 2004), false)
    window.setcheck(window.find(window.parent(dwID), 2005), false)
    window.show(window.find(window.parent(dwID), 2002), false)
    window.show(window.find(window.parent(dwID), 2003), false)
    window.show(window.find(window.parent(dwID), 2007), true)
    WND_SKIN_SLOT = 1
  end
  return 1
end

function OnCloseEquipView(dwID, dwCmdID, dwParam, pParam)
  window.destroy(WND_EQUIP_VIEW)
  WND_EQUIP_VIEW = 0
  return 1
end
