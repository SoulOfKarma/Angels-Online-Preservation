WND_MESSAGE = 0
MESSAGE_CLICK_CLOCK = 0
MESSAGE_CLICK_LOOP = 0
MAX_OPTION_NUM = 6
MAX_REWARD_NUM = 6
MESSAGE_IS_TALK = 0
MESSAGE_SHOW_OPTION_REWARD = 0
MESSAGE_FACE = 0
MESSAGE_MSG_ID = 0
MESSAGE_OPTION1 = 0
MESSAGE_OPTION2 = 0
MESSAGE_OPTION3 = 0
MESSAGE_OPTION4 = 0
MESSAGE_OPTION5 = 0
MESSAGE_OPTION6 = 0
MESSAGE_REWARD1 = 0
MESSAGE_REWARD2 = 0
MESSAGE_REWARD3 = 0
MESSAGE_REWARD4 = 0
MESSAGE_REWARD5 = 0
MESSAGE_REWARD6 = 0
MESSAGE_REWARDNUM1 = 0
MESSAGE_REWARDNUM2 = 0
MESSAGE_REWARDNUM3 = 0
MESSAGE_REWARDNUM4 = 0
MESSAGE_REWARDNUM5 = 0
MESSAGE_REWARDNUM6 = 0
MESSAGE_SELECT_REWARD = 0
TALK_NEXT = 1
TALK_OPTION1 = 10
TALK_OPTION2 = 11
TALK_OPTION3 = 12
TALK_OPTION4 = 13
TALK_OPTION5 = 14
TALK_OPTION6 = 15
TALK_OPTION7 = 16
TALK_OPTION8 = 17
TALK_OPTION9 = 18
TALK_OPTION10 = 19
TALK_REWARD1 = 20
TALK_REWARD2 = 21
TALK_REWARD3 = 22
TALK_REWARD4 = 23
TALK_REWARD5 = 24
TALK_REWARD6 = 25
TALK_REWARD7 = 26
TALK_REWARD8 = 27
TALK_REWARD9 = 28
TALK_REWARD10 = 29

function ShowMessageWnd()
  local i, w, str, text
  if window.isexist(WND_MESSAGE) == false then
    WND_MESSAGE = window.create(244, 0, 0, SYSTEM_HANDLER)
    text = window.find(WND_MESSAGE, 245)
    if UseBigFont == true then
      window.setwindowsize(WND_MESSAGE, 546, 186)
      window.moveoffset(window.find(WND_MESSAGE, 251), 96, 36)
      window.moveoffset(window.find(WND_MESSAGE, 250), 96, 36)
      window.setfont(text, 2)
      window.setwindowsize(text, 374, 152)
      window.setlines(text, 6)
      window.setlineheight(text, 25)
      if MESSAGE_FACE == 0 then
        window.seticon(text, 10131)
      else
        window.seticon(text, 10130)
      end
    elseif MESSAGE_FACE == 0 then
      window.seticon(text, 251)
    else
      window.seticon(text, 245)
    end
    window.regsetting(WND_MESSAGE, "WND_MESSAGE")
    game.playnpcvoice(voiceHello)
    if game.isdef("PS3") == true then
      game.storemousepos()
    end
  end
  text = window.find(WND_MESSAGE, 245)
  game.settalkmessage(text, MESSAGE_MSG_ID)
  window.seticon(window.find(WND_MESSAGE, 251), 14000 + MESSAGE_FACE)
  if MESSAGE_FACE == 0 then
    if UseBigFont == true then
      window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - 320 - 96, SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
    else
      window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - 320, SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
    end
  else
    window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - window.width(WND_MESSAGE), SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
  end
  MESSAGE_IS_TALK = 1
  MESSAGE_SHOW_OPTION_REWARD = 0
  window.show(window.find(WND_MESSAGE, 246), false)
  window.show(window.find(WND_MESSAGE, 247), false)
  window.show(window.find(WND_MESSAGE, 248), false)
  window.show(window.find(WND_MESSAGE, 249), false)
  window.show(window.find(WND_MESSAGE, 484), false)
  window.show(window.find(WND_MESSAGE, 485), false)
  window.show(window.find(WND_MESSAGE, 486), false)
  window.show(window.find(WND_MESSAGE, 487), false)
  window.show(window.find(WND_MESSAGE, 488), false)
  window.show(window.find(WND_MESSAGE, 489), false)
  window.show(window.find(WND_MESSAGE, 250), false)
  window.show(window.find(WND_MESSAGE, 523), false)
  window.show(window.find(WND_MESSAGE, 524), false)
end

function ShowMessageWndIndo()
  local i, w, str
  local bigline = 0
  if window.isexist(WND_MESSAGE) == false then
    WND_MESSAGE = window.create(244, 0, 0, SYSTEM_HANDLER)
    window.regsetting(WND_MESSAGE, "WND_MESSAGE")
    game.playnpcvoice(voiceHello)
    if game.isdef("PS3") == true then
      game.storemousepos()
    end
  end
  bigline = game.settalkmessage(window.find(WND_MESSAGE, 245), MESSAGE_MSG_ID)
  window.seticon(window.find(WND_MESSAGE, 251), 14000 + MESSAGE_FACE)
  if MESSAGE_FACE == 0 then
    if bigline == 1 then
      window.seticon(window.find(WND_MESSAGE, 28013), 30705)
    else
      window.seticon(window.find(WND_MESSAGE, 28013), 251)
    end
    window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - 320, SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
  else
    if bigline == 1 then
      window.seticon(window.find(WND_MESSAGE, 28013), 30706)
    else
      window.seticon(window.find(WND_MESSAGE, 28013), 245)
    end
    window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - window.width(WND_MESSAGE), SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
  end
  MESSAGE_IS_TALK = 1
  MESSAGE_SHOW_OPTION_REWARD = 0
  window.show(window.find(WND_MESSAGE, 246), false)
  window.show(window.find(WND_MESSAGE, 247), false)
  window.show(window.find(WND_MESSAGE, 248), false)
  window.show(window.find(WND_MESSAGE, 249), false)
  window.show(window.find(WND_MESSAGE, 484), false)
  window.show(window.find(WND_MESSAGE, 485), false)
  window.show(window.find(WND_MESSAGE, 486), false)
  window.show(window.find(WND_MESSAGE, 487), false)
  window.show(window.find(WND_MESSAGE, 488), false)
  window.show(window.find(WND_MESSAGE, 489), false)
  window.show(window.find(WND_MESSAGE, 250), false)
  window.show(window.find(WND_MESSAGE, 523), false)
  window.show(window.find(WND_MESSAGE, 524), false)
end

function ShowMessageWndBig()
  local i, w, str
  local bigline = 0
  if window.isexist(WND_MESSAGE) == false then
    WND_MESSAGE = window.create(244, 0, 0, SYSTEM_HANDLER)
    window.regsetting(WND_MESSAGE, "WND_MESSAGE")
    game.playnpcvoice(voiceHello)
    if game.isdef("PS3") == true then
      game.storemousepos()
    end
  end
  w = window.find(WND_MESSAGE, 245)
  if game.isdef("__MALAYSIA") == true then
    window.seticon(w, 0)
  end
  bigline = game.settalkmessage(w, MESSAGE_MSG_ID)
  window.seticon(window.find(WND_MESSAGE, 251), 14000 + MESSAGE_FACE)
  if MESSAGE_FACE == 0 then
    if bigline == 1 then
      window.seticon(window.find(WND_MESSAGE, 10121), 10121)
    else
      window.seticon(window.find(WND_MESSAGE, 10121), 251)
    end
    window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - 320, SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
  else
    if bigline == 1 then
      window.seticon(window.find(WND_MESSAGE, 10121), 10122)
    else
      window.seticon(window.find(WND_MESSAGE, 10121), 245)
    end
    window.move(WND_MESSAGE, SYSTEM_SCREEN_WIDTH - window.width(WND_MESSAGE), SYSTEM_SCREEN_HEIGHT - window.height(WND_MESSAGE))
  end
  MESSAGE_IS_TALK = 1
  MESSAGE_SHOW_OPTION_REWARD = 0
  window.show(window.find(WND_MESSAGE, 246), false)
  window.show(window.find(WND_MESSAGE, 247), false)
  window.show(window.find(WND_MESSAGE, 248), false)
  window.show(window.find(WND_MESSAGE, 249), false)
  window.show(window.find(WND_MESSAGE, 484), false)
  window.show(window.find(WND_MESSAGE, 485), false)
  window.show(window.find(WND_MESSAGE, 486), false)
  window.show(window.find(WND_MESSAGE, 487), false)
  window.show(window.find(WND_MESSAGE, 488), false)
  window.show(window.find(WND_MESSAGE, 489), false)
  window.show(window.find(WND_MESSAGE, 250), false)
  window.show(window.find(WND_MESSAGE, 523), false)
  window.show(window.find(WND_MESSAGE, 524), false)
end

function ShowOption(dwOption, dwResID, nPosY)
  local w = window.find(WND_MESSAGE, dwResID)
  if 0 < dwOption then
    if UseBigFont == true then
      window.setfont(w, 2)
    end
    window.show(w, true)
    window.settitle(w, game.getstring(dwOption))
    window.move(w, window.left(w), nPosY)
  else
    window.show(w, false)
  end
end

function ShowReward(dwReward, nNum, dwResID)
  local w = window.find(WND_MESSAGE, dwResID)
  if 0 < dwReward then
    window.show(w, true)
    local y
    if UseBigFont == true then
      y = window.top(WND_MESSAGE) + 132
    else
      y = window.top(WND_MESSAGE) + 100
    end
    window.move(w, window.left(WND_MESSAGE) + (dwResID - 484) * 40 + 30, y)
    window.seticon(w, game.getitemicon(dwReward))
    window.settitleint(w, nNum)
    if nNum == 0 then
      window.settitle(w, "")
    end
  else
    window.show(w, false)
  end
end

function DestroyMessageWnd()
  if window.isexist(WND_MESSAGE) == true then
    window.destroy(WND_MESSAGE)
    MESSAGE_IS_TALK = 0
    game.playnpcvoice(voiceGoodbye)
    if game.isdef("PS3") == true then
      game.restoremousepos()
    end
  end
  if window.isexist(WND_CONFIRM_REWARD) then
    window.destroy(WND_CONFIRM_REWARD)
    WND_CONFIRM_REWARD = 0
    SELECT_REWARD = 0
    game.playnpcvoice(voiceGoodbye)
  end
end

function OnUpdateMessage(dwID, dwCmdID, dwParam, pParam)
  local t, w, y
  if window.isexist(WND_MESSAGE) == false then
    return 1
  end
  w = window.find(WND_MESSAGE, 245)
  if game.isdef("__SP_DICE") then
    ShowDiceWnd()
  end
  if window.ismessageend(w) and MESSAGE_SHOW_OPTION_REWARD == 0 then
    y = window.top(w) + window.getlines(w) * window.getlineheight(w)
    local dd
    if UseBigFont == true then
      dd = 18
    else
      dd = 14
    end
    ShowOption(MESSAGE_OPTION2, 247, y + dd)
    ShowOption(MESSAGE_OPTION3, 248, y + dd * 2)
    ShowOption(MESSAGE_OPTION4, 249, y + dd * 3)
    ShowOption(MESSAGE_OPTION5, 523, y + dd * 4)
    ShowOption(MESSAGE_OPTION6, 524, y + dd * 5)
    ShowOption(MESSAGE_OPTION1, 246, y)
    ShowReward(MESSAGE_REWARD2, MESSAGE_REWARDNUM2, 485)
    ShowReward(MESSAGE_REWARD3, MESSAGE_REWARDNUM3, 486)
    ShowReward(MESSAGE_REWARD4, MESSAGE_REWARDNUM4, 487)
    ShowReward(MESSAGE_REWARD5, MESSAGE_REWARDNUM5, 488)
    ShowReward(MESSAGE_REWARD6, MESSAGE_REWARDNUM6, 489)
    ShowReward(MESSAGE_REWARD1, MESSAGE_REWARDNUM1, 484)
    if MESSAGE_OPTION1 == 0 and MESSAGE_SELECT_REWARD == 0 then
      w = window.find(WND_MESSAGE, 250)
      window.show(w, true)
      window.setfocus(w, true)
    end
    MESSAGE_SHOW_OPTION_REWARD = 1
  end
  t = window.getclock() - MESSAGE_CLICK_CLOCK
  w = window.find(WND_MESSAGE, 250)
  if 200 <= t then
    if MESSAGE_CLICK_LOOP == 0 then
      window.moveoffset(w, 0, -5)
    else
      window.moveoffset(w, 0, 5)
    end
    MESSAGE_CLICK_LOOP = 1 - MESSAGE_CLICK_LOOP
    MESSAGE_CLICK_CLOCK = window.getclock()
  end
  return 1
end

function OnMessageOption(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  game.talkaction(TALK_OPTION1 + appdata)
  return 1
end

function OnRewardMoveIn(dwID, dwCmdID, dwParam, pParam)
  if MESSAGE_SELECT_REWARD == 1 then
    window.moveoffset(window.find(WND_MESSAGE, dwCmdID), 0, -5)
  end
  return 1
end

function OnRewardMoveOut(dwID, dwCmdID, dwParam, pParam)
  if MESSAGE_SELECT_REWARD == 1 then
    window.moveoffset(window.find(WND_MESSAGE, dwCmdID), 0, 5)
  end
  return 1
end

WND_CONFIRM_REWARD = 0
SELECT_REWARD = 0

function OnSelectReward(dwID, dwCmdID, dwParam, pParam)
  if MESSAGE_SELECT_REWARD == 1 then
    if window.isexist(WND_CONFIRM_REWARD) then
      return 1
    end
    SELECT_REWARD = TALK_REWARD1 + window.getappdata(dwID)
    WND_CONFIRM_REWARD = window.create(552, 0, 0, SYSTEM_HANDLER)
    window.move(WND_CONFIRM_REWARD, window.left(dwID) + window.width(dwID) / 2 - 50, window.top(dwID) - 15)
  end
  return 1
end

function OnConfirmReward(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_CONFIRM_REWARD) then
    game.talkaction(SELECT_REWARD)
    window.destroy(WND_CONFIRM_REWARD)
    WND_CONFIRM_REWARD = 0
    SELECT_REWARD = 0
  end
  return 1
end
