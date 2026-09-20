WND_GUILD = 0
WND_REGISTER_GUILD = 0
WND_GUILD_X = -1
WND_GUILD_Y = -1
WND_CONFIRM = 0
GUILD_BULLETIN_CLOCK = 0
GUILD_DATA_CLOCK = 0
GUILD_MEMBERS_CLOCK = 0
QUERY_GUILD_INTERVAL = 30000
GUILD_DEFAULT_LOGO = 0
GUILD_CAN_CONTRIB_ONLY = 0
GUILD_SORT_KIND = 0
GUILD_SORT_DIR = 0
GLD_EVENT_OK = 0
GLD_EVENT_JOIN = 1
GLD_EVENT_KICK = 2
GLD_EVENT_LEAVE = 3
GLD_EVENT_PROMOTE = 4
GLD_EVENT_DEMOTE = 5
GLD_EVENT_ABDICATE = 6
GLD_EVENT_DISMISS = 7
GLD_EVENT_CHANGE_PERM = 8
GLD_EVENT_SET_RANK_NAME = 9
GLD_EVENT_UPDATE_BULLETIN = 10
GLD_EVENT_GET_BULLETIN = 11
GLD_EVENT_GET_GUILDDATA = 12
GLD_EVENT_GET_MEMBERS = 13
GLD_EVENT_GIVEUP_REGION = 14
GLD_EVENT_BECOME_LEADER = 15
GLD_EVENT_CREATE_GUILD = 16
GLD_EVENT_UPDATE_LOGO = 17
GUILD_RANK_CHIEF = 0
GUILD_RANK_VICECHIEF = 1
GUILD_RANK_OFFICER = 2
GUILD_RANK_MEMBER = 3
GUILD_PERM_WITHDRAW_ITEM = 1
GUILD_PERM_WITHDRAW_MONEY = 2
GUILD_PERM_INVITE = 65536
GUILD_PERM_KICK = 131072
GUILD_PERM_PROMOTE = 262144
GUILD_PERM_DEMOTE = 524288
GUILD_PERM_ABDICATE = 1048576
GUILD_PERM_DISMISS = 2097152
GUILD_PERM_SET_RANK_NAME = 4194304
GUILD_PERM_CHANGE_PERM = 8388608
GUILD_PERM_UPDATE_BULLETIN = 16777216
GUILD_PERM_UPDATE_LOGO = 33554432

function CreateGuildWnd()
  if game.inguild() == false then
    if window.isvisible(WND_GUILD) then
      window.show(WND_GUILD, false)
    end
    game.shownoguildmsg()
    return
  end
  if window.isexist(WND_GUILD) then
    if window.isvisible(WND_GUILD) then
      window.show(WND_GUILD, false)
      return
    else
      window.show(WND_GUILD, true)
    end
  else
    WND_GUILD = window.create(572, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_GUILD_X or 0 > WND_GUILD_Y then
      window.move(WND_GUILD, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
    else
      window.move(WND_GUILD, WND_GUILD_X, WND_GUILD_Y)
    end
    window.regsetting(WND_GUILD, "WND_GUILD")
    window.regcustom(WND_GUILD, "GUILD_CAN_CONTRIB_ONLY")
    window.setradio(window.find(WND_GUILD, 576), 0)
    window.setcheck(window.find(WND_GUILD, 612), true)
    game.initguildwnd()
  end
  GetGuildData()
  GetGuildMembers()
  GetGuildBulletin()
  game.updateguildwnd()
  return 1
end

function OnGuildClose()
  if window.isexist(WND_GUILD) then
    window.show(WND_GUILD, false)
    return 0
  end
end

function GetGuildBulletin()
  if window.getclock() - GUILD_BULLETIN_CLOCK >= QUERY_GUILD_INTERVAL then
    game.guildcommand(GLD_EVENT_GET_BULLETIN, 0, 0)
    GUILD_BULLETIN_CLOCK = window.getclock()
  end
end

function GetGuildData()
  if window.getclock() - GUILD_DATA_CLOCK >= QUERY_GUILD_INTERVAL then
    game.guildcommand(GLD_EVENT_GET_GUILDDATA, 0, 0)
    GUILD_DATA_CLOCK = window.getclock()
  end
end

function GetGuildMembers()
  if window.getclock() - GUILD_MEMBERS_CLOCK >= QUERY_GUILD_INTERVAL then
    game.guildcommand(GLD_EVENT_GET_MEMBERS, 0, 0)
    GUILD_MEMBERS_CLOCK = window.getclock()
  end
end

function OnGuildCheck(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  local page = window.find(Wnd, 579)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 580)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 581)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 693)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, appdata)
  window.show(page, true)
  if appdata == 579 then
    GetGuildBulletin()
    game.updateguildwnd()
  elseif appdata == 580 then
    GetGuildData()
    game.updateguildwnd()
  elseif appdata == 581 then
    GetGuildMembers()
    game.updateguildwnd()
  elseif appdata == 693 then
    game.updateguildwnd()
  end
  return 1
end

function OnUpdateGuildBulletin(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.find(window.parent(dwID), 583)
  game.guildcommand(GLD_EVENT_UPDATE_BULLETIN, 0, 0, window.gettitle(w))
  return 1
end

function OnUploadGuildLogo(dwID, dwCmdID, dwParam, pParam)
  game.uploadguildlogo()
  return 1
end

function OnDefaultGuildLogo(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
    return 1
  end
  WND_CONFIRM = window.create(799, window.parent(dwID), 0, 0)
  window.show(WND_CONFIRM, true)
  return 1
end

function OnSortMembers(dwID, dwCmdID, dwParam, pParam)
  local dw, appdata
  window.show(window.find(window.parent(dwID), 617), false)
  window.show(window.find(window.parent(dwID), 618), false)
  window.show(window.find(window.parent(dwID), 619), false)
  window.show(window.find(window.parent(dwID), 620), false)
  appdata = window.getappdata(dwID)
  if appdata == GUILD_SORT_KIND then
    GUILD_SORT_DIR = 1 - GUILD_SORT_DIR
  else
    GUILD_SORT_KIND = appdata
  end
  dw = window.find(window.parent(dwID), 617 + GUILD_SORT_KIND)
  if GUILD_SORT_DIR == 0 then
    window.seticon(dw, 3271)
  else
    window.seticon(dw, 3272)
  end
  window.show(dw, true)
  game.updateguildwnd()
  return 1
end

function OnSelectMember(dwID, dwCmdID, dwParam, pParam)
  UpdateGuildButton()
  return 1
end

function OnDefaultGuildLogoMoveIn(dwID, dwCmdID, dwParam, pParam)
  local x, y, appdata, n
  appdata = window.getappdata(dwID)
  n = appdata % 4
  x = window.left(window.parent(dwID)) + 5 + n * 54
  y = window.top(window.parent(dwID)) + 5 + (appdata - n) / 4 * 54
  window.move(window.find(window.parent(dwID), 800), x, y)
  return 1
end

function OnSelectDefaultGuildLogo(dwID, dwCmdID, dwParam, pParam)
  GUILD_DEFAULT_LOGO = dwCmdID - 800
  if window.isexist(WND_REGISTER_GUILD) then
    window.seticon(window.find(WND_REGISTER_GUILD, 681), dwCmdID)
  elseif window.isexist(WND_GUILD) then
    window.seticon(window.find(WND_GUILD, 610), dwCmdID)
    game.defaultguildlogo()
    game.guildcommand(GLD_EVENT_UPDATE_LOGO, 0, GUILD_DEFAULT_LOGO)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnGuildInvite(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
  end
  WND_CONFIRM = window.create(632, window.parent(dwID), 0, 0)
  window.moveoffset(WND_CONFIRM, window.width(WND_GUILD) / 2 - 85, window.height(WND_GUILD) / 2 - 50)
  return 1
end

function OnGuildInviteEx_OK(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.find(window.parent(dwID), 634)
  game.guildinvite(window.gettitle(w))
  window.destroy(window.parent(dwID))
  return 1
end

function OnJoinGuild_OK(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_JOIN, 0, 1)
  window.destroy(window.parent(dwID))
  return 1
end

function OnJoinGuild_Deny(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_JOIN, 0, 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnGuildConfirm_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnKickMember(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
  end
  WND_CONFIRM = window.create(637, window.parent(dwID), 0, 0)
  window.settitle(window.find(WND_CONFIRM, 638), game.getstring(644, game.getcurmembername()))
  window.moveoffset(WND_CONFIRM, window.width(WND_GUILD) / 2 - 85, window.height(WND_GUILD) / 2 - 50)
  return 1
end

function OnKickMember_OK(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_KICK, game.getcurmemberid(), 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnPromote(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_PROMOTE, game.getcurmemberid(), 0)
  return 1
end

function OnDemote(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_DEMOTE, game.getcurmemberid(), 0)
  return 1
end

function OnAbdicate(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
  end
  WND_CONFIRM = window.create(641, window.parent(dwID), 0, 0)
  window.settitle(window.find(WND_CONFIRM, 642), game.getstring(645, game.getcurmembername()))
  window.moveoffset(WND_CONFIRM, window.width(WND_GUILD) / 2 - 85, window.height(WND_GUILD) / 2 - 50)
  return 1
end

function OnAbdicate_OK(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_ABDICATE, game.getcurmemberid(), 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnGiveupRegion(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
  end
  WND_CONFIRM = window.create(644, window.parent(dwID), 0, 0)
  window.settitle(window.find(WND_CONFIRM, 645), game.getstring(646, game.getcurmembername()))
  window.moveoffset(WND_CONFIRM, window.width(WND_GUILD) / 2 - 85, window.height(WND_GUILD) / 2 - 50)
  return 1
end

function OnGiveupRegion_OK(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_GIVEUP_REGION, 0, 0)
  window.destroy(window.parent(dwID))
  return 1
end

function OnLeaveGuild(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM) then
    window.destroy(WND_CONFIRM)
  end
  WND_CONFIRM = window.create(647, window.parent(dwID), 0, 0)
  if game.isallowguild(GUILD_PERM_DISMISS) then
    window.settitle(window.find(WND_CONFIRM, 648), game.getstring(648))
  else
    window.settitle(window.find(WND_CONFIRM, 648), game.getstring(647))
  end
  window.moveoffset(WND_CONFIRM, window.width(WND_GUILD) / 2 - 85, window.height(WND_GUILD) / 2 - 50)
  return 1
end

function OnLeaveGuild_OK(dwID, dwCmdID, dwParam, pParam)
  if game.isallowguild(GUILD_PERM_DISMISS) then
    game.guildcommand(GLD_EVENT_DISMISS, 0, 0)
  else
    game.guildcommand(GLD_EVENT_LEAVE, 0, 0)
  end
  window.destroy(window.parent(dwID))
  OnGuildClose()
  return 1
end

function OnQueryMember(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function UpdateGuildButton()
  local dw
  if window.isexist(WND_GUILD) == false then
    return
  end
  dw = window.find(WND_GUILD, 579)
  window.enable(window.find(dw, 583), game.isallowguild(GUILD_PERM_UPDATE_BULLETIN))
  window.enable(window.find(dw, 584), game.isallowguild(GUILD_PERM_UPDATE_BULLETIN))
  dw = window.find(WND_GUILD, 580)
  window.enable(window.find(dw, 586), game.isallowguild(GUILD_PERM_UPDATE_LOGO))
  window.enable(window.find(dw, 587), game.isallowguild(GUILD_PERM_UPDATE_LOGO))
  window.enable(window.find(dw, 598), game.isallowguild(GUILD_PERM_SET_RANK_NAME))
  window.enable(window.find(dw, 599), game.isallowguild(GUILD_PERM_SET_RANK_NAME))
  window.enable(window.find(dw, 600), game.isallowguild(GUILD_PERM_SET_RANK_NAME))
  window.enable(window.find(dw, 601), game.isallowguild(GUILD_PERM_SET_RANK_NAME))
  window.enable(window.find(dw, 602), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 603), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 604), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 605), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 606), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 607), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 608), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  window.enable(window.find(dw, 609), game.isallowguild(GUILD_PERM_CHANGE_PERM))
  dw = window.find(WND_GUILD, 581)
  window.enable(window.find(dw, 624), game.isallowguild(GUILD_PERM_INVITE))
  window.enable(window.find(dw, 625), game.isallowguild(GUILD_PERM_KICK))
  window.enable(window.find(dw, 626), game.isallowguild(GUILD_PERM_PROMOTE))
  window.enable(window.find(dw, 627), game.isallowguild(GUILD_PERM_DEMOTE))
  window.enable(window.find(dw, 628), game.isallowguild(GUILD_PERM_ABDICATE))
  window.enable(window.find(dw, 629), game.isallowguild(GUILD_PERM_DISMISS))
  window.enable(window.find(dw, 630), true)
  if game.isallowguild(GUILD_PERM_DISMISS) == true then
    window.settooltiptext(window.find(dw, 630), game.getstring(671))
  else
    window.settooltiptext(window.find(dw, 630), game.getstring(670))
  end
end

function OnInputRankName(dwID, dwCmdID, dwParam, pParam)
  game.guildcommand(GLD_EVENT_SET_RANK_NAME, 0, window.getappdata(dwID), window.gettitle(dwID))
  return 1
end

function OnCheckGuildPerm(dwID, dwCmdID, dwParam, pParam)
  local nRank, nPerm, appdata
  appdata = window.getappdata(dwID)
  nPerm = appdata % 10
  nRank = (appdata - nPerm) / 10
  game.changeguildperm(nRank, nPerm, window.ischeck(dwID))
  return 1
end

function OnCheckShowOffline(dwID, dwCmdID, dwParam, pParam)
  game.updateguildwnd()
  return 1
end

function CreateRegisterGuildWnd()
  if window.isexist(WND_REGISTER_GUILD) then
    return
  end
  if game.isdef("__PAD_CONTROL") == false then
    WND_REGISTER_GUILD = window.create(674, 0, 0, SYSTEM_HANDLER)
  else
    WND_REGISTER_GUILD = window.create(674, 0, wsPopup, SYSTEM_HANDLER)
  end
  window.move(WND_REGISTER_GUILD, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  window.settitle(window.find(WND_REGISTER_GUILD, 676), game.getplayername())
  return 1
end

function OnRegisterGuild_OK(dwID, dwCmdID, dwParam, pParam)
  game.createguild(window.gettitle(window.find(WND_REGISTER_GUILD, 678)), GUILD_DEFAULT_LOGO)
  return 1
end

function OnRegisterGuild_Cancel(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_REGISTER_GUILD) then
    window.destroy(WND_REGISTER_GUILD)
  end
  return 1
end

function OnGuildOption(dwID, dwCmdID, dwParam, pParam)
  local w, t
  CHAT_CLICK_NAME = game.getguildoptionname(dwID, dwParam)
  if CHAT_CLICK_NAME ~= "NULL" then
    w = window.create(686, 0, 0, SYSTEM_HANDLER)
    t = window.find(w, 687)
    window.settitle(t, CHAT_CLICK_NAME)
    local x, y = window.getcursorpos()
    window.limitmove(w, x, y)
    if 0 < game.getpartnernum() then
      if GROUP_DROPITEM_TYPE == 0 then
        window.enable(window.find(w, 690), false)
      else
        window.enable(window.find(w, 689), false)
      end
    end
  end
  return 1
end

function OnClickContribItem(dwID, dwCmdID, dwParam, pParam)
  local n
  n = game.getcontribnum()
  if n == 0 then
    n = 1
  elseif n == 1 then
    n = 0
  end
  game.setcontribnum(n)
  return 1
end

function OnContribScroll(dwID, dwCmdID, dwParam, pParam)
  game.setcontribnum(dwParam)
  return 1
end

function OnContribEdit(dwID, dwCmdID, dwParam, pParam)
  game.setcontribnum(window.gettitleint(dwID))
  return 1
end

function OnCheckCanContribOnly(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    GUILD_CAN_CONTRIB_ONLY = 1
  else
    GUILD_CAN_CONTRIB_ONLY = 0
  end
  game.updatecontriblist()
  return 1
end

function OnContribConfirm(dwID, dwCmdID, dwParam, pParam)
  local parent = window.parent(dwID)
  local w = window.create(703, parent, 0, 0)
  window.move(w, window.left(parent) + (window.width(parent) - window.width(w)) / 2, window.top(parent) + (window.height(parent) - window.height(w)) / 2)
  return 1
end

function OnGuildContrib(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.guildcontrib()
  return 1
end

function OnCancelContrib(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnEnterFarmMap(dwID, dwCmdID, dwParam, pParam)
  game.enterfarmmap()
  return 1
end

function OnFarmHelp(dwID, dwCmdID, dwParam, pParam)
  game.farmhelp()
  return 1
end
