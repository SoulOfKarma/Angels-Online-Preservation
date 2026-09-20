SWITCH_SKILLEXP = 1
SWITCH_CHARINFO = 1
WND_CHAR_INFO = 0
WND_CHAR_INFO_X = -1
WND_CHAR_INFO_Y = -1

function CreateCharInfoWnd()
  local w
  WND_CHAR_INFO = window.create(158, 0, 0, SYSTEM_HANDLER)
  if WND_CHAR_INFO_X ~= -1 and WND_CHAR_INFO_Y ~= -1 then
    window.move(WND_CHAR_INFO, WND_CHAR_INFO_X, WND_CHAR_INFO_Y)
  end
  if game.isdef("__CARD") == true then
    window.create(180, WND_CHAR_INFO, 0)
  end
  if game.isdef("__MY_HOUSE") == true then
    window.create(27017, WND_CHAR_INFO, 0)
  end
  if game.isdef("__ACHIEVEMENT") == true then
    window.create(28116, WND_CHAR_INFO, 0)
  end
  if game.isdef("__ONLINEREWARD") == true then
    CreateOnlineRewardButton(WND_CHAR_INFO)
  end
  local nShiftX = 0
  if game.isdef("__ROBOT") == true then
    window.create(181, WND_CHAR_INFO, 0)
  else
    nShiftX = nShiftX - 28
  end
  if game.isdef("__ITEM_FUSE") == true then
    local hFuseWnd = window.create(15002, WND_CHAR_INFO, 0)
    if nShiftX ~= 0 then
      window.moveoffset(hFuseWnd, nShiftX, 0)
    end
  else
    nShiftX = nShiftX - 37
  end
  if game.isdef("__PACHINKO") == true then
    local hPachinkoWnd = window.create(26101, WND_CHAR_INFO, 0)
    if nShiftX ~= 0 then
      window.moveoffset(hPachinkoWnd, nShiftX, 0)
    end
  else
    nShiftX = nShiftX - 25
  end
  if game.isdef("__CLOTHES_AND_MONEY") == true then
    local hPD = CreatePDCompButton(WND_CHAR_INFO)
    if nShiftX ~= 0 then
      window.moveoffset(hPD, nShiftX, 0)
    end
  else
    nShiftX = nShiftX - 36
  end
  w = window.find(WND_CHAR_INFO, 179)
  window.setbmpicon(w, "bmp\\head01.tga", "bmp\\headmask.tga")
  window.regsetting(WND_CHAR_INFO, "WND_CHAR_INFO")
  window.regcustom(WND_CHAR_INFO, "SWITCH_SKILLEXP")
  window.regcustom(WND_CHAR_INFO, "SWITCH_CHARINFO")
  window.regcustom(WND_CHAR_INFO, "WND_COMMAND_HIDE")
  window.regcustom(WND_CHAR_INFO, "SYSTEM_CHANNEL_SIZE")
  window.regcustom(WND_CHAR_INFO, "SYSTEM_CUR_CHANNEL")
end

function OnLockCharInfo(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    window.modifystyle(window.parent(dwID), 0, wsMoveable)
  else
    window.modifystyle(window.parent(dwID), wsMoveable, 0)
  end
  return 1
end

function UpdateCharInfoWnd()
  local w1, w2, b, x, y, ChkBtn
  ChkBtn = window.find(WND_CHAR_INFO, 164)
  if SWITCH_SKILLEXP == 1 then
    window.setcheck(ChkBtn, true)
  else
    window.setcheck(ChkBtn, false)
  end
  ChkBtn = window.find(WND_CHAR_INFO, 165)
  if SWITCH_CHARINFO == 1 then
    window.setcheck(ChkBtn, true)
  else
    window.setcheck(ChkBtn, false)
  end
  x = window.left(WND_CHAR_INFO)
  y = window.top(WND_CHAR_INFO)
  w1 = window.find(WND_CHAR_INFO, 263)
  w2 = window.find(WND_CHAR_INFO, 266)
  if SWITCH_SKILLEXP == 1 or SWITCH_CHARINFO == 1 then
    b = true
    if game.isdef("__PEAK_LV_SYSTEM") == true then
      if SWITCH_SKILLEXP == 1 and SWITCH_CHARINFO == 1 then
        window.move(w2, x, y + 386)
      elseif SWITCH_SKILLEXP == 1 then
        window.move(w2, x, y + 218)
      else
        window.move(w2, x, y + 256)
      end
    elseif SWITCH_SKILLEXP == 1 and SWITCH_CHARINFO == 1 then
      window.move(w2, x, y + 344)
    elseif SWITCH_SKILLEXP == 1 then
      window.move(w2, x, y + 176)
    else
      window.move(w2, x, y + 256)
    end
  else
    b = false
  end
  window.show(w1, b)
  window.show(w2, b)
  w1 = window.find(WND_CHAR_INFO, 264)
  if SWITCH_SKILLEXP == 1 then
    b = true
  else
    b = false
  end
  window.show(w1, b)
  w1 = window.find(WND_CHAR_INFO, 265)
  if SWITCH_CHARINFO == 1 then
    b = true
  else
    b = false
  end
  window.show(w1, b)
  if SWITCH_SKILLEXP == 1 then
    if game.isdef("__PEAK_LV_SYSTEM") == true then
      window.move(w1, x, y + 218)
    else
      window.move(w1, x, y + 176)
    end
  else
    window.move(w1, x, y + 88)
  end
end

function OnSkillExps(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    SWITCH_SKILLEXP = 1
  else
    SWITCH_SKILLEXP = 0
  end
  UpdateCharInfoWnd()
  return 1
end

function OnCharInfo(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    SWITCH_CHARINFO = 1
  else
    SWITCH_CHARINFO = 0
  end
  UpdateCharInfoWnd()
  return 1
end
