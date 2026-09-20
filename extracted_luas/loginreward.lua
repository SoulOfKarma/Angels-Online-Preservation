WND_LOGINREWARD_BTN = 0
WND_LOGINREWARD = 0
CURRENT_LOGIN_REWARD_ID = 0

function CreateLoginRewardButton(parent)
end

function RepositionLoginRewardButton(parent)
  local x, y
  x = window.left(parent) - 10
  y = window.top(parent) + window.height(parent) + 4
  window.move(WND_LOGINREWARD_BTN, x, y)
end

function ShowLoginReward(rewardid)
  local button, i, count, itemid, itemnum, canGet, str
  CURRENT_LOGIN_REWARD_ID = rewardid
  count = game.getloginrewardcount(rewardid)
  for i = 0, 5 do
    button = window.find(WND_LOGINREWARD, 24637 + i)
    if i < count then
      itemid = game.getloginrewarditem(rewardid, i)
      itemnum = game.getloginrewarditemnum(rewardid, i)
      window.seticon(button, game.getitemicon(itemid))
      window.settitle(button, itemnum)
      window.setappdata(button, itemid)
    else
      window.seticon(button, 0)
      window.settitle(button, "")
      window.setappdata(button, 0)
    end
  end
  button = window.find(WND_LOGINREWARD, 24636)
  canGet = game.cangetreward(rewardid)
  if canGet == 1 then
    window.enable(button, true)
  else
    window.enable(button, false)
  end
  if canGet == -1 then
    window.settitle(button, game.getstring(3258))
  else
    window.settitle(button, game.getstring(3257))
  end
end

function OnUpdateLoginReward()
  local button, str
  if window.isexist(WND_LOGINREWARD) == true then
    str = game.getmonthstring()
    str = str .. game.getstring(3242)
    text = window.find(WND_LOGINREWARD, 24629)
    window.settitle(text, str)
    str = game.getlogindaysthismonth()
    str = str .. game.getstring(3243)
    text = window.find(WND_LOGINREWARD, 24644)
    window.settitle(text, str)
    button = window.find(WND_LOGINREWARD, 24636)
    canGet = game.cangetreward(CURRENT_LOGIN_REWARD_ID)
    if canGet == 1 then
      window.enable(button, true)
    else
      window.enable(button, false)
    end
    if canGet == -1 then
      window.settitle(button, game.getstring(3258))
    else
      window.settitle(button, game.getstring(3257))
    end
  end
end

function OnClickLoginReward(dwID, dwCmdID, dwParam, pParam)
  local x, y, button, i, text, rewardid, str
  if window.isexist(WND_LOGINREWARD) == false then
    WND_LOGINREWARD = window.create(24628, 0, 0)
    x = window.left(dwID) - window.width(WND_LOGINREWARD)
    y = window.top(dwID)
    window.move(WND_LOGINREWARD, x, y)
    str = game.getmonthstring()
    str = str .. game.getstring(3242)
    text = window.find(WND_LOGINREWARD, 24629)
    window.settitle(text, str)
    str = game.getlogindaysthismonth()
    str = str .. game.getstring(3243)
    text = window.find(WND_LOGINREWARD, 24644)
    window.settitle(text, str)
    button = window.find(WND_LOGINREWARD, 24631)
    window.setradio(button, 0)
    rewardid = window.getappdata(button)
    ShowLoginReward(rewardid)
  end
  return 1
end

function OnClickLoginDays(dwID, dwCmdID, dwParam, pParam)
  local rewardid
  rewardid = window.getappdata(dwID)
  ShowLoginReward(rewardid)
  return 1
end

function OnClickGetLoginReward(dwID, dwCmdID, dwParam, pParam)
  if CURRENT_LOGIN_REWARD_ID ~= 0 then
    game.netcommand(54, CURRENT_LOGIN_REWARD_ID)
  end
  return 1
end

function OnTooltipLoginReward(dwID, dwCmdID, dwParam, pParam)
  local itemid
  itemid = window.getappdata(dwID)
  game.setitemtooltip(dwID, itemid)
  return 1
end
