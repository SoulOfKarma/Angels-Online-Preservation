WND_PARTNER_SUMMON = 0
WND_GROUP = 0
WND_PARTNER = 0
WND_GROUPINVITE_EX = 0
WND_PARTNER_CMD = 0
WND_PARTNER_MAGIC = 0
WND_GROUP_X = -1
WND_GROUP_Y = -1
MAX_PARTNER_NUM = 4
GROUP_DROPITEM_TYPE = 0
PARTNER_CMD_IDX = -1

function ShowPartnerWnd(nCnt)
  local i, w, w2, w3
  if window.isexist(WND_PARTNER) == false then
    WND_PARTNER = window.create(277, 0, 0, SYSTEM_HANDLER)
    for i = 0, MAX_PARTNER_NUM - 1 do
      w = window.find(WND_PARTNER, 278 + i)
      game.initpartnerWnd(i, window.find(w, 286 + i * 2))
    end
    window.move(WND_PARTNER, SYSTEM_SCREEN_WIDTH - window.width(WND_PARTNER), window.top(WND_PARTNER))
    window.regsetting(WND_PARTNER, "WND_PARTNER")
  end
  for i = 0, MAX_PARTNER_NUM - 1 do
    w = window.find(WND_PARTNER, 278 + i)
    if nCnt > i then
      w2 = window.find(w, 285 + i * 2)
      game.setgroupimage(w2, i)
      window.show(w, true)
      w3 = window.find(w, 668)
      if game.getmapid() == game.getpartnermapid(i) then
        window.show(w3, false)
      else
        window.show(w3, true)
        window.modifyiconattrib(w3, ICON_ATTRIB_MIXER, 0)
      end
    else
      window.show(w, false)
    end
  end
end

function OnPartnerCommand(dwID, dwCmdID, dwParam, pParam)
  local idx, c, w
  idx = window.getappdata(dwID)
  PARTNER_CMD_IDX = idx
  c = game.getcursormode()
  if c == CURSOR_MODE_CASTTARGET or c == CURSOR_MODE_CASTDEAD then
    game.castonpartner(idx)
  end
  if c == CURSOR_MODE_USEITEM2PARTNER then
    game.useitemonpartner(idx)
  end
  game.setcursormode(CURSOR_MODE_NORMAL)
  return 1
end

function OnPartnerCommandEx(dwID, dwCmdID, dwParam, pParam)
  local idx, c, w
  idx = window.getappdata(dwID)
  PARTNER_CMD_IDX = idx
  c = game.getcursormode()
  if c == CURSOR_MODE_GROUPPROMOTE then
    game.grouppromote(idx)
  elseif c == CURSOR_MODE_GROUPKICK then
    game.groupkick(idx)
  else
    OnPartnerMenu(idx)
  end
  game.setcursormode(CURSOR_MODE_NORMAL)
  return 1
end

function OnPartnerMenu(idx)
  if window.isexist(WND_PARTNER_CMD) == false then
    WND_PARTNER_CMD = window.create(282, 0, 0, SYSTEM_HANDLER)
    window.regsetting(WND_PARTNER_CMD, "WND_PARTNER_CMD")
  end
  x, y = window.getsysmousexy()
  x = x - 15
  y = y + 5
  if x > SYSTEM_SCREEN_WIDTH - window.width(WND_PARTNER_CMD) then
    x = SYSTEM_SCREEN_WIDTH - window.width(WND_PARTNER_CMD)
  end
  if y > SYSTEM_SCREEN_HEIGHT - window.height(WND_PARTNER_CMD) then
    y = SYSTEM_SCREEN_HEIGHT - window.height(WND_PARTNER_CMD)
  end
  window.move(WND_PARTNER_CMD, x, y)
  if game.isgroupleader() then
    window.enable(window.find(WND_PARTNER_CMD, 316), true)
    window.enable(window.find(WND_PARTNER_CMD, 317), true)
  else
    window.enable(window.find(WND_PARTNER_CMD, 316), false)
    window.enable(window.find(WND_PARTNER_CMD, 317), false)
  end
end

function OnGroupLeaveCmd(dwID, dwCmdID, dwParam, pParam)
  game.groupleave()
  window.destroy(window.parent(dwID))
  return 1
end

function OnGroupPromoteCmd(dwID, dwCmdID, dwParam, pParam)
  if PARTNER_CMD_IDX ~= -1 and PARTNER_CMD_IDX < MAX_PARTNER_NUM then
    game.grouppromote(PARTNER_CMD_IDX)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnGroupKickCmd(dwID, dwCmdID, dwParam, pParam)
  if PARTNER_CMD_IDX ~= -1 and PARTNER_CMD_IDX < MAX_PARTNER_NUM then
    game.groupkick(PARTNER_CMD_IDX)
  end
  window.destroy(window.parent(dwID))
  return 1
end

function OnPartnerTooltip(dwID, dwCmdID, dwParam, pParam)
  local w, idx
  idx = window.getappdata(dwID)
  window.settooltiptext(dwID, game.getpartnername(idx))
  return 1
end

function CreateGroupWnd()
  local w, n
  if window.isexist(WND_GROUP) == false then
    WND_GROUP = window.create(293, 0, 0, SYSTEM_HANDLER)
    if 0 > WND_GROUP_X or 0 > WND_GROUP_Y then
      window.move(WND_GROUP, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
    else
      window.move(WND_GROUP, WND_GROUP_X, WND_GROUP_Y)
    end
    window.regsetting(WND_GROUP, "WND_GROUP")
  else
    window.destroy(WND_GROUP)
    WND_GROUP = 0
    return
  end
  w = window.find(WND_GROUP, 295)
  window.setradio(w, GROUP_DROPITEM_TYPE)
  UpdateGroupButton()
  return 1
end

function UpdateGroupButton()
  local n
  if window.isexist(WND_GROUP) == false then
    return
  end
  n = game.getpartnernum()
  if 0 < n then
    window.enable(window.find(WND_GROUP, 297), false)
    window.enable(window.find(WND_GROUP, 309), false)
    window.enable(window.find(WND_GROUP, 300), true)
    if game.isgroupleader() then
      window.enable(window.find(WND_GROUP, 298), true)
      window.enable(window.find(WND_GROUP, 299), true)
      window.enable(window.find(WND_GROUP, 301), true)
      if n < MAX_PARTNER_NUM then
        window.enable(window.find(WND_GROUP, 297), true)
        window.enable(window.find(WND_GROUP, 309), true)
      end
    else
      window.enable(window.find(WND_GROUP, 298), false)
      window.enable(window.find(WND_GROUP, 299), false)
      window.enable(window.find(WND_GROUP, 301), false)
    end
    if GROUP_DROPITEM_TYPE == 0 then
      window.show(window.find(WND_GROUP, 295), true)
      window.show(window.find(WND_GROUP, 296), false)
    else
      window.show(window.find(WND_GROUP, 295), false)
      window.show(window.find(WND_GROUP, 296), true)
    end
  else
    window.enable(window.find(WND_GROUP, 297), true)
    window.enable(window.find(WND_GROUP, 309), true)
    window.enable(window.find(WND_GROUP, 298), false)
    window.enable(window.find(WND_GROUP, 299), false)
    window.enable(window.find(WND_GROUP, 300), false)
    window.enable(window.find(WND_GROUP, 301), false)
    window.show(window.find(WND_GROUP, 295), true)
    window.show(window.find(WND_GROUP, 296), true)
  end
end

function OnGroupCloseWnd()
  WND_GROUP = 0
  return 1
end

function OnGroupSetType1(dwID, dwCmdID, dwParam, pParam)
  local w
  GROUP_DROPITEM_TYPE = 0
  return 1
end

function OnGroupSetType2(dwID, dwCmdID, dwParam, pParam)
  local w
  GROUP_DROPITEM_TYPE = 1
  return 1
end

function OnGroupInvite(dwID, dwCmdID, dwParam, pParam)
  game.setcursormode(CURSOR_MODE_GROUPINVITE)
  return 1
end

function OnGroupInviteEx(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_GROUPINVITE_EX) then
    return
  end
  WND_GROUPINVITE_EX = window.create(310, window.parent(dwID), 0, 0)
  window.moveoffset(WND_GROUPINVITE_EX, window.width(WND_GROUP) / 2 - 85, window.height(WND_GROUP) / 2 - 50)
  return 1
end

function OnGroupInviteEx_OK(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.find(window.parent(dwID), 312)
  game.groupinvite(window.gettitle(w), GROUP_DROPITEM_TYPE)
  window.destroy(window.parent(dwID))
  return 1
end

function OnGroupInviteEx_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  return 1
end

function OnGroupPromote(dwID, dwCmdID, dwParam, pParam)
  game.setcursormode(CURSOR_MODE_GROUPPROMOTE)
  return 1
end

function OnGroupKick(dwID, dwCmdID, dwParam, pParam)
  game.setcursormode(CURSOR_MODE_GROUPKICK)
  return 1
end

function OnGroupLeave(dwID, dwCmdID, dwParam, pParam)
  game.groupleave()
  return 1
end

function OnGroupDisband(dwID, dwCmdID, dwParam, pParam)
  game.groupdisband()
  return 1
end

function OnGroupAccept(dwID, dwCmdID, dwParam, pParam)
  game.groupjoin()
  window.destroy(window.parent(dwID))
  return 1
end

function OnGroupDeny(dwID, dwCmdID, dwParam, pParam)
  game.groupdeny()
  window.destroy(window.parent(dwID))
  return 1
end

function OnPartnerMoveIn(dwID, dwCmdID, dwParam, pParam)
  local w, idx, nWidth
  idx = window.getappdata(dwID)
  nGood = game.getpartnermagicnum(idx, 0)
  nBad = game.getpartnermagicnum(idx, 1)
  if nGood <= 0 and 0 >= nBad then
    return 1
  end
  if window.isexist(WND_PARTNER_MAGIC) == false then
    WND_PARTNER_MAGIC = window.create(667, 0, 0, SYSTEM_HANDLER)
    for idx = 0, 9 do
      window.move(window.find(WND_PARTNER_MAGIC, 390 + idx), 5 + idx * 20, 26)
      window.move(window.find(WND_PARTNER_MAGIC, 400 + idx), 5 + idx * 20, 5)
    end
  end
  nWidth = 10
  if nGood > nBad then
    nWidth = nWidth + nGood * 20
  else
    nWidth = nWidth + nBad * 20
  end
  window.setwindowsize(WND_PARTNER_MAGIC, nWidth, window.height(WND_PARTNER_MAGIC))
  window.move(WND_PARTNER_MAGIC, window.left(window.parent(dwID)) - nWidth + 5, window.top(window.parent(dwID)) + 5)
  game.updatemagicstate(idx)
  return 1
end

function OnPartnerMoveOut(dwID, dwCmdID, dwParam, pParam)
  local x, y
  x, y = window.getsysmousexy()
  if window.isexist(WND_PARTNER_MAGIC) == true and window.inrange(WND_PARTNER_MAGIC, x, y) == false then
    window.destroy(WND_PARTNER_MAGIC)
  end
  return 1
end

function CreatePartnerSummonWnd()
  WND_PARTNER_SUMMON = window.create(24250, 0, 0, SYSTEM_HANDLER)
end

function OnPartnerSummonAccept(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(24, 1)
  window.destroy(window.parent(dwID))
  return 1
end

function OnPartnerSummonReject(dwID, dwCmdID, dwParam, pParam)
  game.netcommand(24, 0)
  window.destroy(window.parent(dwID))
  return 1
end
