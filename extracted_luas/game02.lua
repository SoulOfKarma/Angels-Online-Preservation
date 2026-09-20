Wnd_MINIGAME = 0
Wnd_MINIGAME_X = -1
Wnd_MINIGAME_Y = -1
Wnd_MINIGAME02 = 0

function MiniGame02_OnStart(dwID, dwCmdID, dwParam, pParam)
  local MiniGameHelp = window.parent(dwID)
  local PosX = window.left(MiniGameHelp)
  local PosY = window.top(MiniGameHelp)
  window.destroy(MiniGameHelp)
  Wnd_MINIGAME02 = window.create(1101, 0, 0, 0)
  window.move(Wnd_MINIGAME02, PosX, PosY)
  game.setminigamewnd(Wnd_MINIGAME02)
  window.changeregsetting(MiniGameHelp, Wnd_MINIGAME02)
  local MiniGame_Custom = window.find(Wnd_MINIGAME02, 1129)
  local pMiniGame = game.getminigame()
  window.seticustom(MiniGame_Custom, pMiniGame)
  game.start()
  return 1
end

function MiniGame02_OnBack(dwID, dwCmdID, dwParam, pParam)
  game.setnumback()
  return 1
end

function MiniGame02_OnClearAllNum(dwID, dwCmdID, dwParam, pParam)
  game.numclearall()
  return 1
end

function MiniGame02_OnAutoSelectNum(dwID, dwCmdID, dwParam, pParam)
  game.autoselectnum()
  return 1
end

function MiniGame02_OnSendStart(dwID, dwCmdID, dwParam, pParam)
  game.sendstart()
  return 1
end

function MiniGame02_OnContinue_Leave(dwID, dwCmdID, dwParam, pParam)
  local Wnd_Continue = window.parent(dwID)
  window.destroy(Wnd_Continue)
  window.destroy(Wnd_MINIGAME02)
  Wnd_MINIGAME02 = 0
  game.leave()
  return 1
end

function MiniGame02_OnContinue_Ok(dwID, dwCmdID, dwParam, pParam)
  game.initgame()
  game.start()
  return 1
end
