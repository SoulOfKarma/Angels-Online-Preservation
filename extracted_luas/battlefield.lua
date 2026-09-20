WND_CRYSTAL_SCORE_BOARD = 0
WND_RESOURCE_SCORE_BOARD = 0

function CreateCrystalScoreBoardWnd()
  if window.isexist(WND_CRYSTAL_SCORE_BOARD) then
    return 1
  end
  WND_CRYSTAL_SCORE_BOARD = window.create(24401, 0, 0, SYSTEM_HANDLER)
  window.move(WND_CRYSTAL_SCORE_BOARD, SYSTEM_SCREEN_WIDTH / 2 - 90, 50)
  return 1
end

function LockBattleCrystalShortcut(bLock)
  if bLock then
    window.modifystyle(WND_CRYSTAL_SCORE_BOARD, wsTransparent, wsMoveable)
  else
    window.modifystyle(WND_CRYSTAL_SCORE_BOARD, wsMoveable, wsTransparent)
  end
end

function OnLockBattleCrystalShortcut(dwID, dwCmdID, dwParam, pParam)
  BATTLECRYSTAL_SHORTCUT_ISLOCK = window.ischeck(dwID)
  LockBattleCrystalShortcut(BATTLECRYSTAL_SHORTCUT_ISLOCK)
  return 1
end

function CreateResourceAndScoreBoardWnd()
  if window.isexist(WND_RESOURCE_SCORE_BOARD) then
    return 1
  end
  WND_RESOURCE_SCORE_BOARD = window.create(24411, 0, 0, SYSTEM_HANDLER)
  window.move(WND_RESOURCE_SCORE_BOARD, SYSTEM_SCREEN_WIDTH - 170, SYSTEM_SCREEN_HEIGHT - 220)
  return 1
end

function LockBattleResShortcut(bLock)
  if bLock then
    window.modifystyle(WND_RESOURCE_SCORE_BOARD, wsTransparent, wsMoveable)
  else
    window.modifystyle(WND_RESOURCE_SCORE_BOARD, wsMoveable, wsTransparent)
  end
end

function OnLockBattleResShortcut(dwID, dwCmdID, dwParam, pParam)
  BATTLERES_SHORTCUT_ISLOCK = window.ischeck(dwID)
  LockBattleResShortcut(BATTLERES_SHORTCUT_ISLOCK)
  return 1
end
