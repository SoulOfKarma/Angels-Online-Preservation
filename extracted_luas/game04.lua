Wnd_MINIGAME04 = 0

function MiniGame04_OnStart(dwID, dwCmdID, dwParam, pParam)
  local MiniGameHelp = window.parent(dwID)
  local PosX = window.left(MiniGameHelp)
  local PosY = window.top(MiniGameHelp)
  window.destroy(MiniGameHelp)
  Wnd_MINIGAME04 = window.create(8001, 0, 0, 0)
  window.move(Wnd_MINIGAME04, PosX, PosY)
  game.setminigamewnd(Wnd_MINIGAME04)
  window.changeregsetting(MiniGameHelp, Wnd_MINIGAME04)
  local MiniGame_Custom = window.find(Wnd_MINIGAME04, 8015)
  local pMiniGame = game.getminigame()
  window.seticustom(MiniGame_Custom, pMiniGame)
  game.start()
  return 1
end

function MiniGame04_OnPass(dwID, dwCmdID, dwParam, pParam)
  game.game04pass()
  return 1
end

function MiniGame04_OnSurrender(dwID, dwCmdID, dwParam, pParam)
  game.game04surrender()
  return 1
end

function MiniGame04_OnContinue_Leave(dwID, dwCmdID, dwParam, pParam)
  local Wnd_Continue = window.parent(dwID)
  window.destroy(Wnd_Continue)
  window.destroy(Wnd_MINIGAME04)
  Wnd_MINIGAME04 = 0
  game.leave()
  return 1
end

function MiniGame04_OnContinue_Ok(dwID, dwCmdID, dwParam, pParam)
  game.initgame04()
  game.start()
  return 1
end
