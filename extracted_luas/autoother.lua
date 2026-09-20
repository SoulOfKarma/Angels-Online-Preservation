AO_BOL_ISAUTOINVITE = 4001
AO_BOL_ISAUTOACCEPT = 4002
AO_BOL_ISAUTOGROUP = 4003
AO_BOL_ISAUTOFOLLOW = 4004
AO_INT_AUTOINVITEEXP = 4005
AO_INT_AUTOACCEPTEXP = 4006
AO_STR_AUTOFOLLOWNAME = 4007
AO_STRLIST_GROUPLIST = 4008
AO_BOL_ISAUTOSUPPORT = 4009
AO_INT_SUPPORTPERCENTAGE = 4010
AO_BOL_ISONLYSUPPORTFELLOW = 4011
AO_INT_SUPPORTSKILL = 4012
AO_INT_SUPPORTSKILLTYPE = 4013

function CreateAutoOtherWnd(WND_AUTOOTHER)
  window.trace("CreateAutoOtherWnd")
  LoadAutoOtherSetting()
  local w = window.find(WND_AUTOOTHER, 2459)
  game.assistclearmagicitem(w)
  LoadAutoSupportSetting()
  return 1
end

function LoadAutoOtherSetting()
  LoadButtonSetting(2402, AO_BOL_ISAUTOINVITE)
  LoadButtonSetting(2405, AO_BOL_ISAUTOACCEPT)
  LoadButtonSetting(2408, AO_BOL_ISAUTOGROUP)
  LoadButtonSetting(2421, AO_BOL_ISAUTOFOLLOW)
  LoadStaticSetting(2403, AO_INT_AUTOINVITEEXP)
  LoadStaticSetting(2406, AO_INT_AUTOACCEPTEXP)
  LoadEditSetting(2422, AO_STR_AUTOFOLLOWNAME)
  LoadListSetting(2411, AO_STRLIST_GROUPLIST)
  game.autootherloadfriendlist(WND_AUTOOTHER)
  game.autootherloadnearplayer(WND_AUTOOTHER)
  return 1
end

function LoadButtonSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  window.setcheck(w, game.getrobotvar_bool(defID))
  return 1
end

function LoadStaticSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  window.settitle(w, game.getstring(1959 + game.getrobotvar_int(defID)))
  return 1
end

function LoadEditSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  if game.getrobotvar_string(AO_STR_AUTOFOLLOWNAME) then
    window.settitle(w, game.getrobotvar_string(defID))
  end
  return 1
end

function LoadListSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  local num = game.robotvar_getnum_list(defID)
  if num then
    window.clearlist(w)
    for i = 0, num - 1 do
      window.insertitemstr(w, game.getrobotvar_stringlist(defID, i), 0)
    end
  end
  return 1
end

function OnCheckAutoInvite(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    game.setrobotvar_bool(AO_BOL_ISAUTOINVITE, true)
  else
    game.setrobotvar_bool(AO_BOL_ISAUTOINVITE, false)
  end
  return 1
end

function OnCheckAutoAccept(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    game.setrobotvar_bool(AO_BOL_ISAUTOACCEPT, true)
  else
    game.setrobotvar_bool(AO_BOL_ISAUTOACCEPT, false)
  end
  return 1
end

function OnCheckAutoGroup(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    game.setrobotvar_bool(AO_BOL_ISAUTOGROUP, true)
  else
    game.setrobotvar_bool(AO_BOL_ISAUTOGROUP, false)
  end
  return 1
end

function OnCheckAutoFollow(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    game.setrobotvar_bool(AO_BOL_ISAUTOFOLLOW, true)
  else
    game.setrobotvar_bool(AO_BOL_ISAUTOFOLLOW, false)
  end
  return 1
end

function OnChooseInviteExp(dwID, dwCmdID, dwParam, pParam)
  local w = window.create(2428, WND_AUTOOTHER, 0, 0)
  window.insertitemstr(window.find(w, 2429), game.getstring(1959), 0)
  window.insertitemstr(window.find(w, 2429), game.getstring(1960), 0)
  return 1
end

function OnChooseAcceptExp(dwID, dwCmdID, dwParam, pParam)
  local w = window.create(2430, WND_AUTOOTHER, 0, 0)
  window.insertitemstr(window.find(w, 2431), game.getstring(1959), 0)
  window.insertitemstr(window.find(w, 2431), game.getstring(1960), 0)
  return 1
end

function OnSelectInviteExp(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(AO_INT_AUTOINVITEEXP, dwParam)
  window.settitle(window.find(WND_AUTOOTHER, 2403), game.getstring(1959 + dwParam))
  window.destroy(window.parent(dwID))
  return 1
end

function OnSelectAcceptExp(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(AO_INT_AUTOACCEPTEXP, dwParam)
  window.settitle(window.find(WND_AUTOOTHER, 2406), game.getstring(1959 + dwParam))
  window.destroy(window.parent(dwID))
  return 1
end

function OnRefreshRobotFriendList(dwID, dwCmdID, dwParam, pParam)
  game.autootherloadfriendlist(WND_AUTOOTHER)
  return 1
end

function OnAddGroupList(dwID, dwCmdID, dwParam, pParam)
  local x = window.find(WND_AUTOOTHER, 2413)
  if window.getcheckitem(x) >= 0 then
    local w = window.find(WND_AUTOOTHER, 2411)
    local str = window.getitemtitle(x, window.getcheckitem(x))
    if window.getlistitemnum(w) then
      for i = 0, window.getlistitemnum(w) - 1 do
        if window.getitemtitle(w, i) == str then
          return 1
        end
      end
    end
    game.autootheraddgrouplist(WND_AUTOOTHER)
    game.robotvar_add_stringlist(AO_STRLIST_GROUPLIST, str)
  end
  return 1
end

function OnDelGroupList(dwID, dwCmdID, dwParam, pParam)
  local x = window.find(WND_AUTOOTHER, 2411)
  if window.getcheckitem(x) >= 0 then
    game.removerobotvar_stringlist(AO_STRLIST_GROUPLIST, window.getcheckitem(x))
    game.autootherdelgrouplist(WND_AUTOOTHER)
  end
  return 1
end

function OnAddGroupName(dwID, dwCmdID, dwParam, pParam)
  local w = window.find(WND_AUTOOTHER, 2411)
  if window.getlistitemnum(w) then
    local str = window.gettitle(window.find(WND_AUTOOTHER, 2418))
    if str == "" then
      return 1
    end
    game.autootheraddgroupname(WND_AUTOOTHER, AO_STRLIST_GROUPLIST)
  end
  return 1
end

function OnRefreshRobotNearPlayer(dwID, dwCmdID, dwParam, pParam)
  game.autootherloadnearplayer(WND_AUTOOTHER)
  return 1
end

function OnAddFollowName(dwID, dwCmdID, dwParam, pParam)
  if window.getcheckitem(window.find(WND_AUTOOTHER, 2424)) >= 0 then
    local w = window.find(WND_AUTOOTHER, 2422)
    game.autootheraddfollowname(WND_AUTOOTHER)
    game.setrobotvar_string(AO_STR_AUTOFOLLOWNAME, window.gettitle(w), game.getstrlen(window.gettitle(w)))
  end
  return 1
end

function OnRobotFollowName(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_string(AO_STR_AUTOFOLLOWNAME, window.gettitle(dwID), game.getstrlen(window.gettitle(dwID)))
  return 1
end

WND_AUTOSUPPORT = 0

function CreateAutoSupportWnd()
  if window.isexist(WND_AUTOSUPPORT) then
    window.destroy(WND_AUTOSUPPORT)
    return 1
  end
  WND_AUTOSUPPORT = window.create(2454, 0, 0, SYSTEM_HANDLER)
  local w = window.find(WND_AUTOOTHER, 2459)
  game.assistclearmagicitem(w)
  LoadAutoSupportSetting()
  return 1
end

function LoadSupportButtonSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  window.setcheck(w, game.getrobotvar_bool(defID))
  return 1
end

function LoadSupportEditSetting(wndID, defID)
  local w = window.find(WND_AUTOOTHER, wndID)
  window.settitleint(w, game.getrobotvar_int(defID))
  return 1
end

function LoadAutoSupportSetting()
  LoadSupportButtonSetting(2455, AO_BOL_ISAUTOSUPPORT)
  LoadSupportButtonSetting(2457, AO_BOL_ISONLYSUPPORTFELLOW)
  LoadSupportEditSetting(2456, AO_INT_SUPPORTPERCENTAGE)
  local dwButtonID = window.find(WND_AUTOOTHER, 2459)
  local nType = game.getrobotvar_int(AO_INT_SUPPORTSKILLTYPE)
  local nValue = game.getrobotvar_int(AO_INT_SUPPORTSKILL)
  game.assistsetmagicitem(dwButtonID, nType, nValue)
  return 1
end

function OnCheckAutoSupportButton(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  if 4000 <= dataid and dataid < 5000 then
    game.setrobotvar_bool(dataid, window.ischeck(dwID))
  end
  return 1
end

function OnEditAutoSupportPercentage(dwID, dwCmdID, dwParam, pParam)
  local dataid = window.getappdata(dwID)
  local nLowBoundValue = tonumber(window.gettitle(dwID))
  if nLowBoundValue == nil then
    nLowBoundValue = 0
  elseif nLowBoundValue < 0 then
    nLowBoundValue = 0
  elseif 100 < nLowBoundValue then
    nLowBoundValue = 100
  end
  if 4000 <= dataid and dataid < 5000 then
    game.setrobotvar_int(dataid, nLowBoundValue)
  end
  return 1
end

function OnDropAutoSupportSkill(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local bIsDroped, nType, nValue = game.autootherdropmagic(dwID, pParam)
  if bIsDroped == false then
    return 0
  elseif nType ~= 1 then
    return 0
  end
  game.setrobotvar_int(AO_INT_SUPPORTSKILLTYPE, nType)
  game.setrobotvar_int(AO_INT_SUPPORTSKILL, nValue)
  return 1
end

function OnRClickAutoSupportSkill(dwID, dwCmdID, dwParam, pParam)
  game.assistclearmagicitem(dwID)
  game.setrobotvar_int(AO_INT_SUPPORTSKILLTYPE, 0)
  game.setrobotvar_int(AO_INT_SUPPORTSKILL, 0)
  return 1
end
