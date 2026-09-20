local COMMAND_ANIMATE = false
local COMMAND_ANIMATE_LOOP = 0
local COMMAND_DEFAULT_BUTTON = false
local Y_TEMP = 0

function ShowCommand(bShow)
  local w
  w = window.find(WND_COMMAND, 127)
  if bShow == true then
    if WND_COMMAND_HIDE == 1 then
      window.seticon(w, 128)
      WND_COMMAND_HIDE = 0
      if game.isdef("__PAD_CONTROL") == true then
        game.padsetmenumode(true)
      end
      COMMAND_ANIMATE = true
      COMMAND_ANIMATE_LOOP = window.getloop()
    end
  elseif WND_COMMAND_HIDE == 0 then
    window.seticon(w, 127)
    WND_COMMAND_HIDE = 1
    if game.isdef("__PAD_CONTROL") == true then
      game.padsetmenumode(false)
    end
    COMMAND_ANIMATE = true
    COMMAND_ANIMATE_LOOP = window.getloop()
  end
end

function ShowHideCommand(bDefButton)
  local w
  if COMMAND_ANIMATE == false then
    if WND_COMMAND_HIDE == 0 then
      ShowCommand(false)
    else
      COMMAND_DEFAULT_BUTTON = bDefButton
      if COMMAND_DEFAULT_BUTTON == true then
        w = window.find(WND_COMMAND, 126)
        window.setfocus(w, true)
      end
      ShowCommand(true)
    end
  end
  return WND_COMMAND_HIDE
end

function OnShowHideCommand(dwID, dwCmdID, dwParam, pParam)
  ShowHideCommand(false)
  return 1
end

function OnAnimateCommand(dwID, dwCmdID, dwParam, pParam)
  local x, y, l, w
  if COMMAND_ANIMATE == true then
    l = 14
    y = pParam - COMMAND_ANIMATE_LOOP
    if l < y then
      y = l
    end
    if WND_COMMAND_HIDE == 0 then
      Y_TEMP = WND_COMMAND_Y - 140 * y / l
      window.move(WND_COMMAND, WND_COMMAND_X, Y_TEMP)
    else
      Y_TEMP = WND_COMMAND_Y + 140 * y / l
      window.move(WND_COMMAND, WND_COMMAND_X, Y_TEMP)
    end
    if y == l then
      COMMAND_ANIMATE = false
      WND_COMMAND_Y = Y_TEMP
      if COMMAND_DEFAULT_BUTTON == true and WND_COMMAND_HIDE == 0 then
        w = window.find(WND_COMMAND, 126)
        window.setfocus(w, true)
        COMMAND_DEFAULT_BUTTON = false
      end
    end
  end
  return 1
end

function OnLoadCommand(first)
  local w
  w = window.find(WND_COMMAND, 127)
  COMMAND_ANIMATE = false
  if WND_COMMAND_HIDE == 1 then
    window.seticon(w, 127)
    if first == true then
      WND_COMMAND_Y = WND_COMMAND_Y + 140
    end
    if game.isdef("__PAD_CONTROL") == true then
      game.padsetmenumode(false)
    end
  else
    window.seticon(w, 128)
    if game.isdef("__PAD_CONTROL") == true then
      game.padsetmenumode(true)
    end
  end
  window.move(WND_COMMAND, WND_COMMAND_X, WND_COMMAND_Y)
  return 1
end

function OnCommandMall(dwID, dwCmdID, dwParam, pParam)
  CreateMallWnd()
  return 1
end

function OnPetInlaySlot(dwID, dwCmdID, dwParam, pParam)
  CreateEquipPetNewWnd()
  return 1
end

function OnCommandItem(dwID, dwCmdID, dwParam, pParam)
  if game.isdef("__KOREA") then
    CreateItemWndAndPackageWnd()
  else
    CreateItemWnd()
  end
  return 1
end

function OnCommandEquip(dwID, dwCmdID, dwParam, pParam)
  CreateSkillsWnd()
  return 1
end

function OnCommandEmotion(dwID, dwCmdID, dwParam, pParam)
  CreateEmotionWnd()
  return 1
end

function OnCommandMap(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_STAGEMAP) then
    OnCloseStageMapWnd()
  else
    CreateStageMapWnd()
  end
  return 1
end

function OnCommandFriend(dwID, dwCmdID, dwParam, pParam)
  CreateFriendWnd()
  return 1
end

function OnCommandGroup(dwID, dwCmdID, dwParam, pParam)
  CreateGroupWnd()
  return 1
end

function OnCommandGuild(dwID, dwCmdID, dwParam, pParam)
  CreateGuildWnd()
  return 1
end

function OnCommandQuest(dwID, dwCmdID, dwParam, pParam)
  CreateQuestWnd()
  return 1
end

function OnCommandSystem(dwID, dwCmdID, dwParam, pParam)
  CreateSystemWnd()
  return 1
end

function OnCommandStarCard(dwID, dwCmdID, dwParam, pParam)
  CreateStarCardWnd()
  return 1
end
