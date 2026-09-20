function MiniGame03_OnStart(dwID, dwCmdID, dwParam, pParam)
  local MiniGameHelp = window.parent(dwID)
  
  local x = window.left(MiniGameHelp)
  local y = window.top(MiniGameHelp)
  window.destroy(MiniGameHelp)
  local dwWnd = window.create(9011, 0, 0, 0)
  window.move(dwWnd, x, y)
  game.setminigamewnd(dwWnd)
  window.seticustom(window.find(dwWnd, 9012), game.getminigame())
  window.changeregsetting(MiniGameHelp, dwWnd)
  game.start()
  return 1
end

function MiniGame03_OnSelect(dwID, dwCmdID, dwParam, pParam)
  game.selectcard03(dwID, window.getappdata(dwID))
  return 1
end

function MiniGame03_OnSelect_OK(dwID, dwCmdID, dwParam, pParam)
  game.selectok03()
  return 1
end

function MiniGame03_OnPass(dwID, dwCmdID, dwParam, pParam)
  game.pass03()
  return 1
end
