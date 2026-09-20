AM_BOL_ENABLE_AUTOMALL = 1600
AM_INT_MALL_UPPERLIMIT = 1601
AM_INT_CURRENTPOINT = 1602
AM_INT2LIST_MALLITEM = 1603
AM_STRLIST_SHOPRECORD = 1604
MAX_SHOP_UPPERLIMIT = 99999
MAX_AM_ORDERNUM = 1000
G_BOOL_AUTOMALL_INITIAL = false

function CreateAutoMallWnd(dwID)
  OnCreateAutoMallWnd(dwID)
  return 1
end

function OnCreateAutoMallWnd(dwMainWndHD)
  window.trace("Create AutoMallWnd")
  InitAutoMallWnd(dwMainWndHD)
  return 1
end

function InitAutoMallWnd(dwMainWndHD)
  game.automallrequestmalldata()
  if G_BOOL_AUTOMALL_INITIAL == false then
    game.setrobotvar_bool(AM_BOL_ENABLE_AUTOMALL, false)
    G_BOOL_AUTOMALL_INITIAL = true
  end
  LoadAutoSupplyCheckButton(dwMainWndHD, AM_BOL_ENABLE_AUTOMALL, 10097, true)
  LoadAutoSupplyEditField(dwMainWndHD, AM_INT_MALL_UPPERLIMIT, 10099, 100)
  local dwCumulation = window.find(dwMainWndHD, 10110)
  window.settitle(dwCumulation, game.getrobotvar_int(AM_INT_CURRENTPOINT) .. "/" .. game.getrobotvar_int(AM_INT_MALL_UPPERLIMIT))
  local dwHelp = window.find(dwMainWndHD, 10113)
  window.show(dwHelp, true)
  local dwRecord = window.find(dwMainWndHD, 10107)
  window.show(dwRecord, false)
  return 1
end

function OnCheckAutoMall(dwID, dwCmdID, dwParam, pParam)
  local bIsRun = window.ischeck(dwID)
  if bIsRun == true then
    game.setrobotvar_bool(AM_BOL_ENABLE_AUTOMALL, true)
    window.trace("Enable AutoMall")
  else
    game.setrobotvar_bool(AM_BOL_ENABLE_AUTOMALL, false)
    window.trace("Disable AutoMall")
  end
  return 1
end

function OnEditUpperLimit(dwID, dwCmdID, dwParam, pParam)
  local limit = window.gettitleint(dwID)
  if limit < MAX_SHOP_UPPERLIMIT then
    if limit < 0 then
      limit = 0
    end
    game.setrobotvar_int(AM_INT_MALL_UPPERLIMIT, limit)
  else
    game.setrobotvar_int(AM_INT_MALL_UPPERLIMIT, MAX_SHOP_UPPERLIMIT)
    window.settitle(dwID, MAX_SHOP_UPPERLIMIT)
  end
  window.trace("Set Upper Limit " .. game.getrobotvar_int(AM_INT_MALL_UPPERLIMIT))
  local dwCumulation = window.find(window.parent(dwID), 10110)
  window.settitle(dwCumulation, game.getrobotvar_int(AM_INT_CURRENTPOINT) .. "/" .. game.getrobotvar_int(AM_INT_MALL_UPPERLIMIT))
  return 1
end

function OnClickResetCumulation(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(AM_INT_CURRENTPOINT, 0)
  window.trace("Reset Cumulation " .. game.getrobotvar_int(AM_INT_CURRENTPOINT))
  local dwCumulation = window.find(window.parent(dwID), 10110)
  window.settitle(dwCumulation, "0/" .. game.getrobotvar_int(AM_INT_MALL_UPPERLIMIT))
  return 1
end

function OnEditMallItemNum(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnClickSetMallItemNum(dwID, dwCmdID, dwParam, pParam)
  local dwEditField = window.find(window.parent(dwID), 10105)
  local num = window.gettitleint(dwEditField)
  if num <= MAX_AM_ORDERNUM then
    if num < 0 then
      num = 0
    end
    game.automallchangeordernum(num)
  else
    game.automallchangeordernum(MAX_AM_ORDERNUM)
  end
  window.settitle(dwEditField, 0)
  game.automallloadmallitem()
  return 1
end

function OnClickClearShoppingRecord(dwID, dwCmdID, dwParam, pParam)
  local dwListWndHD = window.find(window.parent(dwID), 10107)
  window.clearlist(dwListWndHD)
  game.robotvar_clear_list(AM_STRLIST_SHOPRECORD)
  return 1
end

function OnClickChangeHelpOrRecord(dwID, dwCmdID, dwParam, pParam)
  local dwHelp = window.find(window.parent(dwID), 10113)
  local dwRecord = window.find(window.parent(dwID), 10107)
  if window.isvisible(dwHelp) == true then
    window.show(dwHelp, false)
    window.show(dwRecord, true)
  else
    window.show(dwHelp, true)
    window.show(dwRecord, false)
  end
  return 1
end
