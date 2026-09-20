WND_REPAIR = 0
WND_REPAIR_X = -1
WND_REPAIR_Y = -1

function OnRepairClose(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(window.find(dwID, 2903))
  game.repairclose()
  window.destroy(WND_REPAIR)
  WND_REPAIR = 0
  if appdata == 1 then
    game.playnpcvoice(voiceThank)
  end
  return 1
end

function OnRepairOne(dwID, dwCmdID, dwParam, pParam)
  game.repairone()
  return 1
end

function OnRepairAll(dwID, dwCmdID, dwParam, pParam)
  game.repairall()
  return 1
end
