WND_CAPTCHA = 0
WND_CAPTCHA_X = -1
WND_CAPTCHA_Y = -1
CAPTCHA_TIMER_START = 0
CAPTCHA_TIMER_INTERVAL = 600
CAPTCHA_STYLE = 0

function CreateCaptchaWnd(nTry, nWaitTime)
  local i, w, w2, w3
  if window.isexist(WND_CAPTCHA) == true then
    window.destroy(WND_CAPTCHA)
  end
  WND_CAPTCHA = window.create(854, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_CAPTCHA_X or 0 > WND_CAPTCHA_Y or WND_CAPTCHA_X > SYSTEM_SCREEN_WIDTH or WND_CAPTCHA_Y > SYSTEM_SCREEN_HEIGHT then
    window.move(WND_CAPTCHA, SYSTEM_SCREEN_WIDTH - window.width(WND_CAPTCHA), SYSTEM_SCREEN_HEIGHT - window.height(WND_CAPTCHA))
  else
    window.move(WND_CAPTCHA, WND_CAPTCHA_X, WND_CAPTCHA_Y)
  end
  window.settitleint(window.find(WND_CAPTCHA, 858), nTry)
  CAPTCHA_TIMER_START = window.getclock()
  CAPTCHA_TIMER_INTERVAL = nWaitTime
  ShowCaptchaStyle(WND_CAPTCHA, CAPTCHA_STYLE)
  window.regsetting(WND_CAPTCHA, "WND_CAPTCHA")
  window.regcustom(WND_CAPTCHA, "CAPTCHA_STYLE")
  return WND_CAPTCHA
end

function OnInputCaptchaAnswer(dwID, dwCmdID, dwParam, pParam)
  OnSendCaptchaAnswer(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnSendCaptchaAnswer(dwID, dwCmdID, dwParam, pParam)
  local w
  w = window.parent(dwID)
  if game.answercaptcha(window.gettitle(window.find(w, 862))) == true then
    WND_CAPTCHA = 0
    window.destroy(w)
  end
  return 1
end

function OnCaptchaTimer(dwID, dwCmdID, dwParam, pParam)
  local str, diff
  if WND_CAPTCHA ~= 0 then
    diff = window.getclockdur(CAPTCHA_TIMER_START, window.getclock()) / 1000
    if diff > CAPTCHA_TIMER_INTERVAL then
      str = "00:00"
    else
      diff = CAPTCHA_TIMER_INTERVAL - diff
      str = string.format("%02d:%02d", diff / 60, diff % 60)
    end
    window.settitle(window.find(dwID, 860), str)
  end
  return 1
end

function OnSwitchCaptchaStyle(dwID, dwCmdID, dwParam, pParam)
  CAPTCHA_STYLE = 1 - CAPTCHA_STYLE
  ShowCaptchaStyle(window.parent(dwID), CAPTCHA_STYLE)
  return 1
end

function ShowCaptchaStyle(w, style)
  local x, y
  x = window.left(w) + 4
  y = window.top(w) + 20
  if style == 0 then
    window.seticon(w, 854)
    window.setwindowsize(w, 216, 220)
    window.show(window.find(w, 855), true)
    window.move(window.find(w, 856), x + 41, y + 100)
    window.move(window.find(w, 857), x + 117, y + 64)
    window.move(window.find(w, 858), x + 185, y + 66)
    window.move(window.find(w, 859), x + 4, y + 64)
    window.move(window.find(w, 860), x + 57, y + 66)
    window.move(window.find(w, 861), x + 35, y + 175)
    window.move(window.find(w, 862), x + 87, y + 177)
    window.move(window.find(w, 863), x + 135, y + 175)
    window.move(window.find(w, 864), x + 61, y + 85)
    window.move(window.find(w, 865), x + 172, y + 91)
  else
    window.seticon(w, 855)
    window.setwindowsize(w, 216, 161)
    window.show(window.find(w, 855), false)
    window.move(window.find(w, 856), x + 41, y + 100 - 59)
    window.move(window.find(w, 857), x + 117, y + 64 - 59)
    window.move(window.find(w, 858), x + 185, y + 66 - 59)
    window.move(window.find(w, 859), x + 4, y + 64 - 59)
    window.move(window.find(w, 860), x + 57, y + 66 - 59)
    window.move(window.find(w, 861), x + 35, y + 175 - 59)
    window.move(window.find(w, 862), x + 87, y + 177 - 59)
    window.move(window.find(w, 863), x + 135, y + 175 - 59)
    window.move(window.find(w, 864), x + 61, y + 85 - 59)
    window.move(window.find(w, 865), x + 172, y + 91 - 59)
  end
end
