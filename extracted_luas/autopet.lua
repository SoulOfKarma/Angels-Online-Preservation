LUA_DROP_TYPE_ALL = 4294967295
AP_BOL_ISAUTOHELPPET = 5000
AP_INT_ISAUTOHELPPET_LOWHP = 5001
AP_INT_ISAUTOHELPPET_SKILLITEM = 5002
AP_BOL_ISAUTOCLOSEPET = 5004
AP_INT_ISAUTOCLOSEPET_LOWHP = 5005
AP_INT_ISAUTOCLOSEPET_LOWFOOD = 5006
AP_INT_ISAUTOCLOSEPET_LOWLOVE = 5007
AP_BOL_ISAUTOTEACHPET = 5008
AP_INT_ISAUTOTEACHPET_RESP = 5009
AP_INT_ISAUTOHELPPET_LOWMP = 5010
AP_INT_ISAUTOHELPPET_SKILLITEM2 = 5011
AP_BOL_INITIAL = 5900

function CreateAutoPetWindow(WND_AUTOPET)
  local w = window.find(WND_AUTOPET, 24607)
  window.setdrop(w, LUA_DROP_TYPE_ALL, 4294967295)
  InitPetWindow(WND_AUTOPET)
  return 1
end

function InitPetWindow(dwMainWndHD)
  local dwttt = window.find(dwMainWndHD, 24601)
  LoadPetCheckButton(dwMainWndHD, AP_BOL_ISAUTOHELPPET, 24601, true)
  LoadPetTextEdit(dwMainWndHD, AP_INT_ISAUTOHELPPET_LOWHP, 24603, 70)
  LoadPetTextEdit(dwMainWndHD, AP_INT_ISAUTOHELPPET_LOWMP, 24622, 40)
  LoadPetCheckButton(dwMainWndHD, AP_BOL_ISAUTOCLOSEPET, 24608, game.getrobotvar_bool(AP_BOL_INITIAL))
  LoadPetTextEdit(dwMainWndHD, AP_INT_ISAUTOCLOSEPET_LOWHP, 24610, 40)
  LoadPetTextEdit(dwMainWndHD, AP_INT_ISAUTOCLOSEPET_LOWFOOD, 24613, 20)
  LoadPetTextEdit(dwMainWndHD, AP_INT_ISAUTOCLOSEPET_LOWLOVE, 24616, 20)
  LoadPetCheckButton(dwMainWndHD, AP_BOL_ISAUTOTEACHPET, 24620, true)
  LoadPetRadioButton(dwMainWndHD, AP_INT_ISAUTOTEACHPET_RESP, 24617, 2)
  local dwButtonID, nType, nValue
  dwButtonID = window.find(dwMainWndHD, 24607)
  nType = game.getrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM)
  nValue = game.getrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM + 1)
  game.assistsetmagicitem(dwButtonID, nType, nValue)
  window.setappdatafordualint(dwButtonID, nType, nValue)
  dwButtonID = window.find(dwMainWndHD, 24625)
  nType = game.getrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2)
  nValue = game.getrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2 + 1)
  game.assistsetmagicitem(dwButtonID, nType, nValue)
  window.setappdatafordualint(dwButtonID, nType, nValue)
  game.setrobotvar_bool(AP_BOL_INITIAL, true)
end

function LoadPetRadioButton(dwMainWndHD, dataid, windowID, defaultvalue)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local nRadio = game.getrobotvar_int(dataid)
  if nRadio == 0 then
    window.setradio(dwSelectedWndHD, defaultvalue - 1)
    game.setrobotvar_int(dataid, defaultvalue - 1)
  else
    window.setradio(dwSelectedWndHD, nRadio - 1)
  end
  return 1
end

function LoadPetCheckButton(dwMainWndHD, dataid, windowID, bInit)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local bIsCheck = game.getrobotvar_bool(dataid)
  if bInit == false then
    bIsCheck = true
  end
  window.setcheck(dwSelectedWndHD, bIsCheck)
  return 1
end

function LoadPetTextEdit(dwMainWndHD, dataid, windowID, defaultvalue)
  local dwSelectedWndHD = window.find(dwMainWndHD, windowID)
  local nLowBoundValue = game.getrobotvar_int(dataid)
  if nLowBoundValue == 0 and game.getrobotvar_bool(AP_BOL_INITIAL) == false then
    window.settitle(dwSelectedWndHD, defaultvalue)
    game.setrobotvar_int(dataid, defaultvalue)
  else
    window.settitle(dwSelectedWndHD, nLowBoundValue)
  end
  return 1
end

function OnAutoPetSaveRadio(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  local radioindex = window.getradio(dwID)
  if 0 < dataid and dataid < 6000 then
    game.setrobotvar_int(dataid, radioindex + 1)
  end
  return 1
end

function OnAutoPetSaveCheck(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  if 0 < dataid and dataid < 6000 then
    game.setrobotvar_bool(dataid, window.ischeck(dwID))
  end
  return 1
end

function OnAutoPetSaveTextEdit(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  local nLowBoundValue = tonumber(window.gettitle(dwID))
  if nLowBoundValue == nil then
    nLowBoundValue = 0
  elseif 100 < nLowBoundValue then
    nLowBoundValue = 100
  elseif nLowBoundValue < 0 then
    nLowBoundValue = 0
  end
  if 0 < dataid and dataid < 6000 then
    game.setrobotvar_int(dataid, nLowBoundValue)
  end
  return 1
end

function OnDropPetMagicItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("Drop" .. dwID .. "-" .. dwCmdID .. "-" .. dwParam)
  local dwMainWndHD = window.parent(dwID)
  local bIsDroped, nType, nValue = game.assistdropmagicitem(dwID, pParam)
  if bIsDroped == false then
    return 0
  end
  window.setappdatafordualint(dwID, nType, nValue)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM, nType)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM + 1, nValue)
  return 1
end

function OnClearPetMagicItem(dwID, dwCmdID, dwParam, pParam)
  game.assistclearmagicitem(dwID)
  window.setappdatafordualint(dwID, 0, 0)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM, 0)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM + 1, 0)
  return 1
end

function OnDropPetMagicItem2(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local bIsDroped, nType, nValue = game.assistdropmagicitem(dwID, pParam)
  if bIsDroped == false then
    return 0
  end
  window.setappdatafordualint(dwID, nType, nValue)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2, nType)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2 + 1, nValue)
  return 1
end

function OnClearPetMagicItem2(dwID, dwCmdID, dwParam, pParam)
  game.assistclearmagicitem(dwID)
  window.setappdatafordualint(dwID, 0, 0)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2, 0)
  game.setrobotvar_int(AP_INT_ISAUTOHELPPET_SKILLITEM2 + 1, 0)
  return 1
end

function OnTooltipPetMagicItem(dwID, dwCmdID, dwParam, pParam)
  local nType, nValue = window.getappdatafordualint(dwID)
  if nType == 0 then
    return 0
  end
  game.ontooltipassistmagicitem(dwID, nType, nValue)
  return 1
end
