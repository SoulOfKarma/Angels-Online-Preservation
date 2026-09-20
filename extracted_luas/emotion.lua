MaxEmotionIcon = 34
WND_EMOTION = 0
WND_EMOTION_X = -1
WND_EMOTION_Y = -1

function CreateEmotionWndBody()
  WND_EMOTION = window.create(3001, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_EMOTION_X or 0 > WND_EMOTION_Y then
    window.move(WND_EMOTION, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_EMOTION, WND_EMOTION_X, WND_EMOTION_Y)
  end
  game.initemotwnd()
  window.regsetting(WND_EMOTION, "WND_EMOTION")
end

function CreateEmotionWnd()
  if window.isexist(WND_EMOTION) then
    window.destroy(WND_EMOTION)
    WND_EMOTION = 0
    return
  end
  CreateEmotionWndBody()
  return 1
end

function CreateEmotionWndUpdate()
  if window.isexist(WND_EMOTION) then
    window.destroy(WND_EMOTION)
    WND_EMOTION = 0
    return
  end
  CreateEmotionWndBody()
  return 1
end

function OnEmotionChaSize(dwID, dwCmdID, dwParam, pParam)
  local OldEmoWnd = window.parent(dwID)
  local AppData = window.getappdata(dwID)
  local PosX = window.left(OldEmoWnd)
  local PosY = window.top(OldEmoWnd)
  window.destroy(OldEmoWnd)
  WND_EMOTION = window.create(AppData, 0, 0, SYSTEM_HANDLER)
  window.move(WND_EMOTION, PosX, PosY)
  window.changeregsetting(OldEmoWnd, WND_EMOTION)
  local w, i
  for i = 3003, 3006 do
    w = window.find(WND_EMOTION, i)
    window.setdrop(w, DROP_TYPE_EMOT, 1)
  end
  if AppData == 3011 then
    local Emotion_List = window.find(WND_EMOTION, 3017)
    for i = 1, 8 do
      window.insertitemstrappnum(Emotion_List, "", 4012 + i - 1, i - 1)
    end
    window.insertitemstrappnum(Emotion_List, "", 4023, 8)
    window.insertitemstrappnum(Emotion_List, "", 4024, 9)
    window.insertitemstrappnum(Emotion_List, "", 4032, 10)
    window.insertitemstrappnum(Emotion_List, "", 4034, 11)
    for i = 13, MaxEmotionIcon do
      if game.getemotbuy(i - 1) == 1 then
        window.insertitemstrappnum(Emotion_List, "", 4012 + game.getemotbyindex(i - 1), i - 1)
      end
    end
  end
  game.initemotwnd()
  return 1
end

function OnDragEmo(dwID, dwCmdID, dwParam, pParam)
  local AppData = window.getitemappdata(dwID, dwParam)
  game.dragemot(dwID, dwCmdID, AppData, pParam)
  return 1
end

function OnUseEmo(dwID, dwCmdID, dwParam, pParam)
  local AppData = window.getitemappdata(dwID, dwParam)
  game.netcommand(1, AppData)
  return 1
end

function OnDropQuickEmo(dwID, dwCmdID, dwParam, pParam)
  game.dropemot(dwCmdID, pParam)
  return 1
end

function OnDragQuickEmo(dwID, dwCmdID, dwParam, pParam)
  local q
  q = dwCmdID - 3003
  if q < 0 then
    q = 0
  elseif 3 < q then
    q = 3
  end
  game.dragquickemot(dwID, dwCmdID, q, pParam)
  return 1
end

function OnDropXQuickEmo(dwID, dwCmdID, dwParam, pParam)
  game.dropxquickemot(pParam)
  return 1
end

function OnUseQuickEmo(dwID, dwCmdID, dwParam, pParam)
  local q
  q = dwCmdID - 3003
  if q < 0 then
    q = 0
  elseif 3 < q then
    q = 3
  end
  game.quickemot(q)
  return 1
end
