WND_MINIGAME_ONCLOSE = 0

function MiniGame01_OnStart(dwID, dwCmdID, dwParam, pParam)
  local MiniGameHelp = window.parent(dwID)
  local x = window.left(MiniGameHelp)
  local y = window.top(MiniGameHelp)
  window.destroy(MiniGameHelp)
  local dwWnd = window.create(1011, 0, 0, 0)
  window.move(dwWnd, x, y)
  game.setminigamewnd(dwWnd)
  window.seticustom(window.find(dwWnd, 1012), game.getminigame())
  window.changeregsetting(MiniGameHelp, dwWnd)
  game.start()
  return 1
end

function MiniGame_OnLeave(dwID, dwCmdID, dwParam, pParam)
  WND_MINIGAME_ONCLOSE = window.create(1091, window.parent(dwID), 0, 0)
  window.moveoffset(WND_MINIGAME_ONCLOSE, window.width(window.parent(dwID)) / 2 - 75, window.height(window.parent(dwID)) / 2 - 26)
  return 1
end

function MiniGame01_OnGiveUp(dwID, dwCmdID, dwParam, pParam)
  game.giveup01()
  return 1
end

function OnGiveUp01_OK(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.start()
  return 1
end

function OnGiveUp01_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.leave()
  return 1
end

function MiniGame_OnClose(dwID, dwCmdID, dwParam, pParam)
  WND_MINIGAME_ONCLOSE = window.create(1091, dwID, 0, 0)
  window.moveoffset(WND_MINIGAME_ONCLOSE, window.width(dwID) / 2 - 75, window.height(dwID) / 2 - 26)
  return 0
end

function OnClose_OK(dwID, dwCmdID, dwParam, pParam)
  WND_MINIGAME_ONCLOSE = window.parent(dwID)
  window.destroy(WND_MINIGAME_ONCLOSE)
  game.leave()
  return 1
end

function OnClose_Cancel(dwID, dwCmdID, dwParam, pParam)
  WND_MINIGAME_ONCLOSE = window.parent(dwID)
  window.destroy(WND_MINIGAME_ONCLOSE)
  return 1
end

function OnChangePage(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local x = window.left(window.parent(dwID))
  local y = window.top(window.parent(dwID))
  window.destroy(window.parent(dwID))
  local PAGE = window.create(appdata, 0, 0, 0)
  window.move(PAGE, x, y)
  game.setminigamewnd(PAGE)
  return 1
end
