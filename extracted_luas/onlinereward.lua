WND_ONLINEREWARD_BTN = 0
ONLINEREWARD_CANGET = false

function CreateOnlineRewardButton(parent)
end

function OnClickOnlineReward(dwID, dwCmdID, dwParam, pParam)
  if ONLINEREWARD_CANGET == true then
    game.netcommand(53, 0)
  end
  return 1
end

function SetOnlineRewardCanGet(canget)
  ONLINEREWARD_CANGET = canget
  if canget == true then
    window.seticon(WND_ONLINEREWARD_BTN, 24627)
  else
    window.seticon(WND_ONLINEREWARD_BTN, 24626)
  end
end
