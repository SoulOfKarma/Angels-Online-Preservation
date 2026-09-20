function OnMarryAskOK(dwID, dwCmdID, dwParam, pParam)
  game.marryaskok(dwID)
  
  window.destroy(window.parent(dwID))
  return 1
end

function OnMarryAskCancel(dwID, dwCmdID, dwParam, pParam)
  game.marryaskcancel(dwID)
  window.destroy(window.parent(dwID))
  return 1
end
