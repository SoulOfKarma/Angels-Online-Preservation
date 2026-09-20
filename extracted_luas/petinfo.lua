WNDID_PET_INFO = 878
SWITCH_PET_INFO = 1
WND_PET_INFO = 0
WND_PET_INFO_X = -1
WND_PET_INFO_Y = -1
WND_PET_ASPECT = 0
PET_CURRENT_AI = 2
PET_COMMAND_GUARD = 0
PET_COMMAND_AGGRESS = 1
PET_COMMAND_PASSIVE = 2
PET_COMMAND_WITHDRAW_GEMEXP = 3
PET_COMMAND_ASPECT_OPTION1 = 4
PET_COMMAND_ASPECT_OPTION2 = 5
PET_COMMAND_ASPECT_OPTION3 = 6
PET_COMMAND_EQUIP = 7
WND_PET_RESURRECT = 0
WND_PET_RESURRECT_X = -1
WND_PET_RESURRECT_Y = -1
WND_PET_EQUIP_WINDOW = 0
WND_BTN_PET_EQUIP_SUIT = 0
BOOL_PET_EQUIP_WINDOW_SHOW = false
WNDID_PET_EQUIP_SUIT = 16102
WNDID_BTN_PET_EQUIP_SUIT = 16119
WND_PET_EQUIP_SUIT_SELECT = 0

function CreatePetInfoWnd()
  local w, bShow, btn
  if WND_PET_INFO == 0 then
    game.petcommand(PET_CURRENT_AI)
  end
  HidePetWnd()
  WND_PET_INFO = window.create(WNDID_PET_INFO, 0, 0, SYSTEM_HANDLER)
  btn = window.find(WND_PET_INFO, 936)
  if SWITCH_PET_INFO == 0 then
    bShow = false
    window.seticon(btn, 936)
  else
    bShow = true
    window.seticon(btn, 937)
  end
  w = window.find(WND_PET_INFO, 880)
  window.show(w, bShow)
  if WND_PET_INFO_X ~= -1 and WND_PET_INFO_Y ~= -1 then
    window.move(WND_PET_INFO, WND_PET_INFO_X, WND_PET_INFO_Y)
  end
  game.updatepetmagicstate()
  if PET_CURRENT_AI == PET_COMMAND_AGGRESS then
    SetPetAI(0)
  elseif PET_CURRENT_AI == PET_COMMAND_GUARD then
    SetPetAI(1)
  else
    SetPetAI(2)
  end
  window.regsetting(WND_PET_INFO, "WND_PET_INFO")
  window.regcustom(WND_PET_INFO, "SWITCH_PET_INFO")
  if game.isdef("__ITEM_FUSE") then
    w = window.find(WND_PET_INFO, 16001)
    window.show(w, bShow)
  end
  WND_BTN_PET_EQUIP_SUIT = window.find(WND_PET_INFO, WNDID_BTN_PET_EQUIP_SUIT)
  WND_PET_EQUIP_WINDOW = window.find(WND_PET_INFO, WNDID_PET_EQUIP_SUIT)
  if game.isdef("__V16_PET_SUIT") then
    ShowPetEquipWnd(BOOL_PET_EQUIP_WINDOW_SHOW)
    window.regsetting(WND_PET_EQUIP_WINDOW, "WND_PET_EQUIP_WINDOW")
    game.inititemwnd(WND_PET_EQUIP_WINDOW, 10)
    UpdatePetSuitStyleCheckBox()
  else
    if WND_BTN_PET_EQUIP_SUIT ~= 0 then
      window.show(WND_BTN_PET_EQUIP_SUIT, false)
    end
    if WND_PET_EQUIP_WINDOW ~= 0 then
      window.show(WND_PET_EQUIP_WINDOW, false)
    end
  end
end

function HidePetWnd()
  if WND_PET_INFO ~= 0 then
    window.destroy(WND_PET_INFO)
    WND_PET_INFO = 0
  end
end

function OnClickPetDetail(dwID, dwCmdID, dwParam, pParam)
  local parent, w, bShow, btn
  parent = window.parent(dwID)
  parent = window.parent(parent)
  btn = window.find(parent, 936)
  if SWITCH_PET_INFO == 1 then
    SWITCH_PET_INFO = 0
    bShow = false
    window.seticon(btn, 936)
  else
    SWITCH_PET_INFO = 1
    bShow = true
    window.seticon(btn, 937)
  end
  w = window.find(parent, 880)
  window.show(w, bShow)
  if game.isdef("__ITEM_FUSE") then
    w = window.find(WND_PET_INFO, 16001)
    window.show(w, bShow)
  end
  if game.isdef("__V16_PET_SUIT") then
    if bShow then
      ShowPetEquipWnd(BOOL_PET_EQUIP_WINDOW_SHOW)
    else
      window.show(WND_PET_EQUIP_WINDOW, false)
      window.show(WND_BTN_PET_EQUIP_SUIT, false)
    end
  end
  return 1
end

function OnClickSelectPetAI(dwID, dwCmdID, dwParam, pParam)
  local w, x, y
  w = window.create(927, 0, 0, SYSTEM_HANDLER)
  window.move(w, window.left(dwID), window.top(dwID) + window.height(dwID) + 1)
  return 1
end

function SetPetAI(index)
  local w
  w = window.find(WND_PET_INFO, 882)
  window.seticon(w, 928 + index)
end

function OnClickPetAI1(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.petcommand(PET_COMMAND_AGGRESS)
  PET_CURRENT_AI = PET_COMMAND_AGGRESS
  return 1
end

function OnClickPetAI2(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.petcommand(PET_COMMAND_GUARD)
  PET_CURRENT_AI = PET_COMMAND_GUARD
  return 1
end

function OnClickPetAI3(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.petcommand(PET_COMMAND_PASSIVE)
  PET_CURRENT_AI = PET_COMMAND_PASSIVE
  return 1
end

function OnClickPetAI4(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.petcommand(PET_COMMAND_EQUIP)
  PET_CURRENT_AI = PET_COMMAND_EQUIP
  return 1
end

function OnPetInput(dwID, dwCmdID, dwParam, pParam)
  game.setpetname()
  return 1
end

function OnConfirmGemExp(dwID, dwCmdID, dwParam, pParam)
  local parent = window.parent(dwID)
  local w = window.create(938, parent, 0, 0)
  window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  return 1
end

function OnWithdrawGemExp(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.petcommand(PET_COMMAND_WITHDRAW_GEMEXP)
  return 1
end

function OnCancelGemExp(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function CreateAskAspectWnd(pStatment, pOption1, pOption2, pOption3)
  DestroyAskAspectWnd()
  if game.isdef("__PAD_CONTROL") == false then
    WND_PET_ASPECT = window.create(931, 0, 0, SYSTEM_HANDLER)
  else
    WND_PET_ASPECT = window.create(931, 0, wsPopup, SYSTEM_HANDLER)
  end
  window.move(WND_PET_ASPECT, (SYSTEM_SCREEN_WIDTH - window.width(WND_PET_ASPECT)) / 2, SYSTEM_SCREEN_HEIGHT - window.height(WND_PET_ASPECT))
  window.settitle(window.find(WND_PET_ASPECT, 932), pStatment)
  window.settitle(window.find(WND_PET_ASPECT, 933), pOption1)
  window.settitle(window.find(WND_PET_ASPECT, 934), pOption2)
  window.settitle(window.find(WND_PET_ASPECT, 935), pOption3)
end

function DestroyAskAspectWnd()
  if window.isexist(WND_PET_ASPECT) == true then
    window.destroy(WND_PET_ASPECT)
  end
end

function OnAspectOption(dwID, dwCmdID, dwParam, pParam)
  local idx
  idx = window.getappdata(dwID)
  if 0 <= idx and idx <= 2 then
    game.petcommand(PET_COMMAND_ASPECT_OPTION1 + idx)
    DestroyAskAspectWnd()
  end
  return 1
end

function CreatePetResurrectWnd()
  if WND_PET_RESURRECT ~= 0 then
    window.destroy(WND_PET_RESURRECT)
    WND_PET_RESURRECT = 0
  end
  if game.isdef("__PAD_CONTROL") == false then
    WND_PET_RESURRECT = window.create(2963, 0, 0, SYSTEM_HANDLER)
  else
    WND_PET_RESURRECT = window.create(2963, 0, wsPopup, SYSTEM_HANDLER)
  end
  if WND_PET_RESURRECT_X ~= -1 and WND_PET_RESURRECT_Y ~= -1 then
    window.move(WND_PET_RESURRECT, WND_PET_RESURRECT_X, WND_PET_RESURRECT_Y)
  end
  window.regsetting(WND_PET_RESURRECT, "WND_PET_RESURRECT")
end

function OnCastPet(dwID, dwCmdID, dwParam, pParam)
  local c
  c = game.getcursormode()
  if c == CURSOR_MODE_CASTTARGET then
    game.castonpet()
  end
  game.setcursormode(CURSOR_MODE_NORMAL)
  return 1
end

PET_MAGICSTATE_TIME = 0

function OnUpdatePetMagicState(dwID, dwCmdID, dwParam, pParam)
  local diff
  diff = window.getclockdur(PET_MAGICSTATE_TIME, window.getclock())
  if 1000 < diff then
    game.updatepetmagicstate()
    PET_MAGICSTATE_TIME = window.getclock()
  end
  return 1
end

function OnOpenPetEquipInterface(dwID, dwCmdID, dwParam, pParam)
  CreatePetEquipWnd()
  return 1
end

function CreatePetEquipWnd()
  if game.isdef("__V16_PET_SUIT") then
    if window.isvisible(WND_PET_EQUIP_WINDOW) then
      ShowPetEquipWnd(false)
    else
      ShowPetEquipWnd(true)
    end
  end
end

function ShowPetEquipWnd(bShow)
  if game.isdef("__V16_PET_SUIT") then
    w = window.find(WND_PET_INFO, 880)
    if window.isvisible(w) then
      if bShow then
        window.show(WND_PET_EQUIP_WINDOW, true)
        window.show(WND_BTN_PET_EQUIP_SUIT, false)
      else
        window.show(WND_PET_EQUIP_WINDOW, false)
        window.show(WND_BTN_PET_EQUIP_SUIT, true)
      end
    else
      window.show(WND_PET_EQUIP_WINDOW, false)
      window.show(WND_BTN_PET_EQUIP_SUIT, false)
    end
    BOOL_PET_EQUIP_WINDOW_SHOW = window.isvisible(WND_PET_EQUIP_WINDOW)
  end
end

function OnChangePetSuitStyle(dwID, dwCmdID, dwParam, pParam)
  if false == game.isdef("__V16_PET_SUIT") then
    return
  end
  if 16121 == dwCmdID and WND_PET_EQUIP_SUIT_SELECT ~= 1 then
    WND_PET_EQUIP_SUIT_SELECT = 1
  elseif 16122 == dwCmdID and WND_PET_EQUIP_SUIT_SELECT ~= 2 then
    WND_PET_EQUIP_SUIT_SELECT = 2
  elseif 16123 == dwCmdID and WND_PET_EQUIP_SUIT_SELECT ~= 3 then
    WND_PET_EQUIP_SUIT_SELECT = 3
  else
    WND_PET_EQUIP_SUIT_SELECT = 0
  end
  game.updatepetequipsuit(WND_PET_EQUIP_SUIT_SELECT)
  return 1
end

function UpdatePetSuitStyleCheckBox()
  if false == game.isdef("__V16_PET_SUIT") then
    return
  end
  local nCheckBox1 = window.find(WND_PET_INFO, 16121)
  local nCheckBox2 = window.find(WND_PET_INFO, 16122)
  local nCheckBox3 = window.find(WND_PET_INFO, 16123)
  window.setcheck(nCheckBox1, false)
  window.setcheck(nCheckBox2, false)
  window.setcheck(nCheckBox3, false)
  if 1 == WND_PET_EQUIP_SUIT_SELECT then
    window.setcheck(nCheckBox1, true)
  elseif 2 == WND_PET_EQUIP_SUIT_SELECT then
    window.setcheck(nCheckBox2, true)
  elseif 3 == WND_PET_EQUIP_SUIT_SELECT then
    window.setcheck(nCheckBox3, true)
  end
end
