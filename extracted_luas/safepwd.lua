function OnSetSafePassword(dwID, dwCmdID, dwParam, pParam)
  window.create(2504, window.parent(dwID), 0, 0)
  
  return 1
end

function OnModifySafePassword(dwID, dwCmdID, dwParam, pParam)
  window.create(2509, window.parent(dwID), 0, 0)
  return 1
end

function OnClearSafePassword(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnSetSafePassword_OK(dwID, dwCmdID, dwParam, pParam)
  game.setsafepassword(window.parent(dwID))
  return 1
end

function OnSafePassword_Cancel(dwID, dwCmdID, dwParam, pParam)
  window.destroy(winddow.parent(dwID))
  return 1
end
