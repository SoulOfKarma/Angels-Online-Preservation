WND_QUICK_COMMAND = 0
WND_QUICK_COMMAND_X = -1
WND_QUICK_COMMAND_Y = -1
QUICK_COMMAND_TYPE = 1
QUICK_COMMAND_X1 = 13
QUICK_COMMAND_Y1 = 94
QUICK_COMMAND_X2 = 210
QUICK_COMMAND_Y2 = 0
QUICK_COMMAND_PAGE = 0

function CreateQuickCmdWnd()
  if QUICK_COMMAND_TYPE == 0 then
    n = 201
    if WND_QUICK_COMMAND_X ~= -1 and WND_QUICK_COMMAND_Y ~= -1 then
      QUICK_COMMAND_X1 = WND_QUICK_COMMAND_X
      QUICK_COMMAND_Y1 = WND_QUICK_COMMAND_Y
    end
    x = QUICK_COMMAND_X1
    y = QUICK_COMMAND_Y1
  else
    n = 182
    if WND_QUICK_COMMAND_X ~= -1 and WND_QUICK_COMMAND_Y ~= -1 then
      QUICK_COMMAND_X2 = WND_QUICK_COMMAND_X
      QUICK_COMMAND_Y2 = WND_QUICK_COMMAND_Y
    end
    x = QUICK_COMMAND_X2
    y = QUICK_COMMAND_Y2
  end
  WND_QUICK_COMMAND = window.create(n, 0, 0, SYSTEM_HANDLER)
  window.move(WND_QUICK_COMMAND, x, y)
  CreateQuickCommandButtons()
  window.regsetting(WND_QUICK_COMMAND, "WND_QUICK_COMMAND")
  window.regcustom(WND_QUICK_COMMAND, "QUICK_COMMAND_TYPE")
  window.regcustom(WND_QUICK_COMMAND, "QUICK_COMMAND_X1")
  window.regcustom(WND_QUICK_COMMAND, "QUICK_COMMAND_Y1")
  window.regcustom(WND_QUICK_COMMAND, "QUICK_COMMAND_X2")
  window.regcustom(WND_QUICK_COMMAND, "QUICK_COMMAND_Y2")
end

function OnLockQuickCommand(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    window.modifystyle(window.parent(dwID), 0, wsMoveable)
  else
    window.modifystyle(window.parent(dwID), wsMoveable, 0)
  end
  return 1
end

function SaveQuickStyle()
  local ox, oy
  ox = window.left(WND_QUICK_COMMAND)
  oy = window.top(WND_QUICK_COMMAND)
  if QUICK_COMMAND_TYPE == 0 then
    QUICK_COMMAND_X1 = ox
    QUICK_COMMAND_Y1 = oy
  else
    QUICK_COMMAND_X2 = ox
    QUICK_COMMAND_Y2 = oy
  end
  return 1
end

function SetQuickStyle()
  local n, x, y, bLock, w, l, ow
  if QUICK_COMMAND_TYPE == 1 then
    x = QUICK_COMMAND_X2
    y = QUICK_COMMAND_Y2
    w = window.find(WND_QUICK_COMMAND, 202)
    n = 182
    l = 183
  else
    x = QUICK_COMMAND_X1
    y = QUICK_COMMAND_Y1
    w = window.find(WND_QUICK_COMMAND, 183)
    n = 201
    l = 202
  end
  bLock = window.ischeck(w)
  ow = WND_QUICK_COMMAND
  window.destroy(WND_QUICK_COMMAND)
  WND_QUICK_COMMAND = 0
  WND_QUICK_COMMAND = window.create(n, 0, 0, SYSTEM_HANDLER)
  window.move(WND_QUICK_COMMAND, x, y)
  CreateQuickCommandButtons()
  window.changeregsetting(ow, WND_QUICK_COMMAND)
  w = window.find(WND_QUICK_COMMAND, l)
  window.setcheck(w, bLock)
  if bLock == true then
    window.modifystyle(window.parent(w), 0, wsMoveable)
  end
  return 1
end

function OnChangeQuickStyle(dwID, dwCmdID, dwParam, pParam)
  local ox, oy
  ox = window.left(WND_QUICK_COMMAND)
  oy = window.top(WND_QUICK_COMMAND)
  if QUICK_COMMAND_TYPE == 0 then
    QUICK_COMMAND_TYPE = 1
    QUICK_COMMAND_X1 = ox
    QUICK_COMMAND_Y1 = oy
    SetQuickStyle()
  else
    QUICK_COMMAND_TYPE = 0
    QUICK_COMMAND_X2 = ox
    QUICK_COMMAND_Y2 = oy
    SetQuickStyle()
  end
  return 1
end

function CreateQuickCommandButtons()
  local x, y, dx, dy, i, w, page
  if QUICK_COMMAND_TYPE == 0 then
    x = 3
    y = 33
    dx = 0
    dy = 31
    page = window.find(WND_QUICK_COMMAND, 204)
  else
    x = 33
    y = 3
    dx = 31
    dy = 0
    page = window.find(WND_QUICK_COMMAND, 185)
  end
  for i = 0, 11 do
    w = window.create(211 + i, WND_QUICK_COMMAND, 0, SYSTEM_HANDLER)
    window.moveoffset(w, x, y)
    x = x + dx
    y = y + dy
    if i == 3 or i == 7 then
      if 0 < dx then
        x = x + 1
      else
        y = y + 1
      end
    end
  end
  if QUICK_COMMAND_PAGE == 0 then
    window.seticon(page, 185)
  else
    window.seticon(page, 186)
  end
  game.initquickkeywnd(WND_QUICK_COMMAND, QUICK_COMMAND_PAGE)
end

function OnChangeQuickPage(dwID, dwCmdID, dwParam, pParam)
  ChangeQuickPage()
  return 1
end

function ChangeQuickPage()
  local page
  if QUICK_COMMAND_TYPE == 0 then
    page = window.find(WND_QUICK_COMMAND, 204)
  else
    page = window.find(WND_QUICK_COMMAND, 185)
  end
  QUICK_COMMAND_PAGE = QUICK_COMMAND_PAGE + 1
  if QUICK_COMMAND_PAGE > 1 then
    QUICK_COMMAND_PAGE = 0
  end
  if QUICK_COMMAND_PAGE == 0 then
    window.seticon(page, 185)
  else
    window.seticon(page, 186)
  end
  game.initquickkeywnd(WND_QUICK_COMMAND, QUICK_COMMAND_PAGE)
end

function OnDragQuickKey(dwID, dwCmdID, dwParam, pParam)
  local q
  q = dwCmdID - 211
  if q < 0 then
    q = 0
  elseif 11 < q then
    q = 11
  end
  game.dragquickkey(dwID, dwCmdID, q, pParam)
  return 1
end

function OnDropQuickKey(dwID, dwCmdID, dwParam, pParam)
  game.dropquickkey(QUICK_COMMAND_PAGE, dwCmdID - 211, pParam)
  return 1
end

function OnDropXQuickKey(dwID, dwCmdID, dwParam, pParam)
  game.dropxquickkey(QUICK_COMMAND_PAGE, pParam)
  return 1
end

function OnUseQuickKey(dwID, dwCmdID, dwParam, pParam)
  local q
  q = dwCmdID - 211
  if q < 0 then
    q = 0
  elseif 11 < q then
    q = 11
  end
  game.usequickkey(QUICK_COMMAND_PAGE, q)
  return 1
end
