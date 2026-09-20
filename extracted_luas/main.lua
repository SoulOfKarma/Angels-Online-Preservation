WND_CHAT = 0
WND_COMMAND = 0
WND_COMMAND_X = -1
WND_COMMAND_Y = -1
WND_COMMAND_HIDE = 0
WND_CHAT_CONTENT_0 = 0
WND_CHAT_CONTENT_1 = 0
WND_CHAT_CONTENT_2 = 0
WND_CHAT_CONTENT_3 = 0
WND_MESSAGE = 0
WND_EXPGOLD = 0
WND_EXPGOLDBACK = 0
SYSTEM_HANDLER = 0
SYSTEM_CHANNEL_SIZE = 3
SYSTEM_CUR_CHANNEL = 0
SYSTEM_CHAT_MAXLINE = 100
SYSTEM_CUR_SPEECH = 0

function CreateMainWnd(handler)
  local n, w, l, x, y, m0, m1, m2, m3
  SYSTEM_HANDLER = handler
  WND_EXPGOLDBACK = window.create(12127, 0, 0, handler)
  window.setmaxline(WND_EXPGOLDBACK, 4)
  window.enablebreakline(WND_EXPGOLDBACK, false)
  window.move(WND_EXPGOLDBACK, 10, 350)
  WND_EXPGOLD = window.find(WND_EXPGOLDBACK, 12128)
  window.setmaxline(WND_EXPGOLD, 4)
  window.enablebreakline(WND_EXPGOLD, false)
  CreateCharInfoWnd()
  UpdateCharInfoWnd()
  if game.isdef("__PEAK_LV_SYSTEM") == true then
    local CharInfoY = window.height(WND_CHAR_INFO) + 350
    window.move(WND_EXPGOLDBACK, 10, CharInfoY)
  end
  if game.isdef("PS3") == false then
    UseBigFont = false
    DefaultUseBigFont = false
  end
  if SYSTEM_CHANNEL_SIZE == 0 then
    n = 152
    m0 = 230
    m1 = 231
    m2 = 232
    m3 = 233
    l = 153
  elseif SYSTEM_CHANNEL_SIZE == 1 then
    n = 101
    m0 = 129
    m1 = 234
    m2 = 235
    m3 = 236
    l = 103
  elseif SYSTEM_CHANNEL_SIZE == 3 then
    n = 143
    m0 = 150
    m1 = 237
    m2 = 238
    m3 = 239
    l = 145
  else
    n = 134
    m0 = 141
    m1 = 240
    m2 = 241
    m3 = 242
    l = 136
  end
  WND_CHAT = window.create(n, 0, 0, handler)
  window.move(WND_CHAT, 0, SYSTEM_SCREEN_HEIGHT - window.height(WND_CHAT) - 6)
  w = window.find(WND_CHAT, l)
  if game.isdef("__PAD_CONTROL") == false then
    window.setalwaysedit(w)
  end
  if m0 ~= 0 then
    WND_CHAT_CONTENT_0 = window.find(WND_CHAT, m0)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_0, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_0, 38)
        window.setworkrange(WND_CHAT_CONTENT_0, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_0, 4)
        window.setlineheight(WND_CHAT_CONTENT_0, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_0, 38)
        window.setworkrange(WND_CHAT_CONTENT_0, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_0, 7)
        window.setlineheight(WND_CHAT_CONTENT_0, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_0, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_0, false)
  else
    WND_CHAT_CONTENT_0 = 0
  end
  if m1 ~= 0 then
    WND_CHAT_CONTENT_1 = window.find(WND_CHAT, m1)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_1, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_1, 38)
        window.setworkrange(WND_CHAT_CONTENT_1, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_1, 4)
        window.setlineheight(WND_CHAT_CONTENT_1, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_1, 38)
        window.setworkrange(WND_CHAT_CONTENT_1, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_1, 7)
        window.setlineheight(WND_CHAT_CONTENT_1, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_1, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_1, false)
  else
    WND_CHAT_CONTENT_1 = 0
  end
  if m2 ~= 0 then
    WND_CHAT_CONTENT_2 = window.find(WND_CHAT, m2)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_2, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_2, 38)
        window.setworkrange(WND_CHAT_CONTENT_2, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_2, 4)
        window.setlineheight(WND_CHAT_CONTENT_2, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_2, 38)
        window.setworkrange(WND_CHAT_CONTENT_2, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_2, 7)
        window.setlineheight(WND_CHAT_CONTENT_2, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_2, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_2, false)
  else
    WND_CHAT_CONTENT_2 = 0
  end
  if m3 ~= 0 then
    WND_CHAT_CONTENT_3 = window.find(WND_CHAT, m3)
    if UseBigFont == true then
      window.setfont(WND_CHAT_CONTENT_3, 2)
      if SYSTEM_CHANNEL_SIZE == 2 then
        window.seticon(window.find(WND_CHAT, 135), 10128)
        window.setwordsperline(WND_CHAT_CONTENT_3, 38)
        window.setworkrange(WND_CHAT_CONTENT_3, 9, 8, 304, 68)
        window.setlines(WND_CHAT_CONTENT_3, 4)
        window.setlineheight(WND_CHAT_CONTENT_3, 17)
      elseif SYSTEM_CHANNEL_SIZE == 3 then
        window.seticon(window.find(WND_CHAT, 144), 10129)
        window.setwordsperline(WND_CHAT_CONTENT_3, 38)
        window.setworkrange(WND_CHAT_CONTENT_3, 9, 4, 304, 119)
        window.setlines(WND_CHAT_CONTENT_3, 7)
        window.setlineheight(WND_CHAT_CONTENT_3, 17)
      end
    end
    window.setmaxline(WND_CHAT_CONTENT_3, SYSTEM_CHAT_MAXLINE)
    window.enablebreakline(WND_CHAT_CONTENT_3, false)
  else
    WND_CHAT_CONTENT_3 = 0
  end
  SetCurSpeechIcon()
  SetCurrentContent()
  w = window.find(WND_CHAT, 108)
  window.setradio(w, SYSTEM_CUR_CHANNEL)
  local first = false
  WND_COMMAND = window.create(116, 0, 0, handler)
  window.setclipping(WND_COMMAND, 0, 0, SYSTEM_SCREEN_WIDTH, SYSTEM_SCREEN_HEIGHT)
  if game.isdef("__PAD_CONTROL") == true then
    WND_COMMAND_X = -1
    WND_COMMAND_Y = -1
    WND_COMMAND_HIDE = 1
  end
  if 0 > WND_COMMAND_X or 0 > WND_COMMAND_Y then
    WND_COMMAND_X = SYSTEM_SCREEN_WIDTH - window.width(WND_COMMAND) - 4
    WND_COMMAND_Y = SYSTEM_SCREEN_HEIGHT - 6
    first = true
  end
  OnLoadCommand(first)
  CreateQuickCmdWnd()
  CreateMiniMapWnd()
  CreateQuestWnd()
end

function DestroyMainWnd()
  window.destroy(WND_CHAR_INFO)
  window.destroy(WND_CHAT)
  window.destroy(WND_COMMAND)
  window.destroy(WND_QUICK_COMMAND)
end

WND_MINIMAP = 0
WND_MINIMAP_X = -1
WND_MINIMAP_Y = -1

function CreateMiniMapWnd()
  if window.isexist(WND_MINIMAP) then
    return
  end
  WND_MINIMAP = window.create(269, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_MINIMAP_X or 0 > WND_MINIMAP_Y then
    window.move(WND_MINIMAP, SYSTEM_SCREEN_WIDTH - window.width(WND_MINIMAP), 0)
  else
    window.move(WND_MINIMAP, WND_MINIMAP_X, WND_MINIMAP_Y)
  end
  game.openmap(0, WND_MINIMAP)
  window.regsetting(WND_MINIMAP, "WND_MINIMAP")
  if game.isdef("__COLLECTION") == true then
    WND_CLTN_BTN = window.create(28201, WND_MINIMAP, 0)
    window.move(WND_CLTN_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_CLTN_BTN) - 3, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__DAILY_EVENT") == true then
    WND_DAILY_BTN = window.create(28318, WND_MINIMAP, 0)
    window.move(WND_DAILY_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_DAILY_BTN) - 39, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__V10_JUMPMAP") == true then
    WND_JUMPMAP_BTN = window.create(28350, WND_MINIMAP, 0)
    window.move(WND_JUMPMAP_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_JUMPMAP_BTN) - 75, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__QUESTION") == true then
    WND_QUESTION_BTN = window.create(24768, WND_MINIMAP, 0)
    window.move(WND_QUESTION_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_QUESTION_BTN) - 111, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__LOGINREWARD") == true then
    CreateLoginRewardButton(WND_MINIMAP)
  end
  if game.isdef("__GVG") == true then
    WND_GVG_BTN = window.create(25156, WND_MINIMAP, 0)
    window.move(WND_GVG_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_GVG_BTN) - 3, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2 + 32)
  end
end

function OnMiniMapClose()
  game.setminimapopen()
  if game.isdef("__COLLECTION") == true then
    window.move(WND_CLTN_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_CLTN_BTN) - 3, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__DAILY_EVENT") == true then
    window.move(WND_DAILY_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_DAILY_BTN) - 39, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__V10_JUMPMAP") == true then
    window.move(WND_JUMPMAP_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_JUMPMAP_BTN) - 75, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__QUESTION") == true then
    window.move(WND_QUESTION_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_QUESTION_BTN) - 111, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2)
  end
  if game.isdef("__LOGINREWARD") == true then
    RepositionLoginRewardButton(WND_MINIMAP)
  end
  if game.isdef("__GVG") == true then
    window.move(WND_GVG_BTN, window.left(WND_MINIMAP) + window.width(WND_MINIMAP) - window.width(WND_GVG_BTN) - 3, window.top(WND_MINIMAP) + window.height(WND_MINIMAP) + 2 + 32)
  end
  return 0
end

WND_STAGEMAP = 0
APPDATA_CHANGE_MAP = 1
MAX_MAPPAGE = 5

function CreateStageMapWnd()
  game.setstagerender(0)
  if window.isexist(WND_STAGEMAP) then
    return
  end
  if game.isdef("__PAD_CONTROL") == false then
    WND_STAGEMAP = window.create(556, 0, 0, SYSTEM_HANDLER)
  else
    WND_STAGEMAP = window.create(556, 0, wsPopup, SYSTEM_HANDLER)
  end
  window.setcheck(window.find(WND_STAGEMAP, 558), game.isshowmapname())
  window.setcheck(window.find(WND_STAGEMAP, 12247), game.isshowguildname())
  window.setcheck(window.find(WND_STAGEMAP, 12248), game.isshowplacename())
  window.setradio(window.find(WND_STAGEMAP, 12245), 0)
  game.setstagemappage(0)
  window.setwindowsize(WND_STAGEMAP, SYSTEM_SCREEN_WIDTH, SYSTEM_SCREEN_HEIGHT)
  window.setwindowsize(window.find(WND_STAGEMAP, 557), SYSTEM_SCREEN_WIDTH - 8, SYSTEM_SCREEN_HEIGHT - 39)
  window.move(window.find(WND_STAGEMAP, 558), SYSTEM_SCREEN_WIDTH - 90, SYSTEM_SCREEN_HEIGHT - 20)
  window.move(window.find(WND_STAGEMAP, 12247), SYSTEM_SCREEN_WIDTH - 166, SYSTEM_SCREEN_HEIGHT - 20)
  window.move(window.find(WND_STAGEMAP, 12248), SYSTEM_SCREEN_WIDTH - 90, SYSTEM_SCREEN_HEIGHT - 20)
  window.move(window.find(WND_STAGEMAP, 12245), window.left(window.find(WND_STAGEMAP, 12245)), SYSTEM_SCREEN_HEIGHT - 19)
  window.move(window.find(WND_STAGEMAP, 12246), window.left(window.find(WND_STAGEMAP, 12246)), SYSTEM_SCREEN_HEIGHT - 19)
  if game.isdef("__KOREA") then
    window.destroy(window.find(WND_STAGEMAP, 10001))
    window.seticon(window.find(WND_STAGEMAP, 10002), 10007)
    window.setwindowsize(window.find(WND_STAGEMAP, 10002), 26, 18)
    window.move(window.find(WND_STAGEMAP, 10002), SYSTEM_SCREEN_WIDTH - 33, SYSTEM_SCREEN_HEIGHT - 40)
    window.setplane(window.find(WND_STAGEMAP, 10002), 4010)
  end
  if game.isdef("__DATA1") then
    window.move(window.find(WND_STAGEMAP, 12899), window.left(window.find(WND_STAGEMAP, 12899)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12899), false)
  end
  if game.isdef("__DATA2MAP") then
    window.move(window.find(WND_STAGEMAP, 12898), window.left(window.find(WND_STAGEMAP, 12898)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12898), false)
  end
  if game.isdef("__DATA3MAP") then
    window.move(window.find(WND_STAGEMAP, 12897), window.left(window.find(WND_STAGEMAP, 12897)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12897), false)
  end
  if game.isdef("__DATA4MAP") then
    window.move(window.find(WND_STAGEMAP, 12896), window.left(window.find(WND_STAGEMAP, 12896)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12896), false)
  end
  if game.isdef("__DATA5MAP") then
    window.move(window.find(WND_STAGEMAP, 12895), window.left(window.find(WND_STAGEMAP, 12895)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12895), false)
  end
  if game.isdef("__DATA6MAP") then
    window.move(window.find(WND_STAGEMAP, 12894), window.left(window.find(WND_STAGEMAP, 12894)), SYSTEM_SCREEN_HEIGHT - 19)
  else
    window.show(window.find(WND_STAGEMAP, 12894), false)
  end
  if game.isdef("__DATA7MAP") then
    window.move(window.find(WND_STAGEMAP, 12909), window.left(window.find(WND_STAGEMAP, 12909)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 12909), false)
  else
    window.show(window.find(WND_STAGEMAP, 12909), false)
  end
  if game.isdef("__DATA8MAP") then
    window.move(window.find(WND_STAGEMAP, 12910), window.left(window.find(WND_STAGEMAP, 12910)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 12910), false)
  else
    window.show(window.find(WND_STAGEMAP, 12910), false)
  end
  if game.isdef("__DATA9MAP") then
    window.move(window.find(WND_STAGEMAP, 12919), window.left(window.find(WND_STAGEMAP, 12919)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 12919), false)
    window.move(window.find(WND_STAGEMAP, 24750), window.left(window.find(WND_STAGEMAP, 24750)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 24750), true)
  else
    window.show(window.find(WND_STAGEMAP, 12919), false)
  end
  if game.isdef("__DATA10MAP") then
    window.move(window.find(WND_STAGEMAP, 12928), window.left(window.find(WND_STAGEMAP, 12928)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 12928), false)
  else
    window.show(window.find(WND_STAGEMAP, 12928), false)
  end
  if game.isdef("__DATA11MAP") then
    window.move(window.find(WND_STAGEMAP, 12929), window.left(window.find(WND_STAGEMAP, 12929)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 12929), false)
  else
    window.show(window.find(WND_STAGEMAP, 12929), false)
  end
  if game.isdef("__DATA12MAP") then
    window.move(window.find(WND_STAGEMAP, 24800), window.left(window.find(WND_STAGEMAP, 24800)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 24800), false)
  else
    window.show(window.find(WND_STAGEMAP, 24800), false)
  end
  if game.isdef("__DATA13MAP") then
    window.move(window.find(WND_STAGEMAP, 25500), window.left(window.find(WND_STAGEMAP, 25500)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25500), false)
  else
    window.show(window.find(WND_STAGEMAP, 25500), false)
  end
  if game.isdef("__DATA14MAP") then
    window.move(window.find(WND_STAGEMAP, 25501), window.left(window.find(WND_STAGEMAP, 25501)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25501), false)
  else
    window.show(window.find(WND_STAGEMAP, 25501), false)
  end
  if game.isdef("__DATA15MAP") then
    window.move(window.find(WND_STAGEMAP, 25502), window.left(window.find(WND_STAGEMAP, 25502)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25502), false)
  else
    window.show(window.find(WND_STAGEMAP, 25502), false)
  end
  if game.isdef("__DATA16MAP") then
    window.move(window.find(WND_STAGEMAP, 25503), window.left(window.find(WND_STAGEMAP, 25503)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25503), false)
  else
    window.show(window.find(WND_STAGEMAP, 25503), false)
  end
  if game.isdef("__DATA17MAP") then
    window.move(window.find(WND_STAGEMAP, 25504), window.left(window.find(WND_STAGEMAP, 25504)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25504), false)
  else
    window.show(window.find(WND_STAGEMAP, 25504), false)
  end
  if game.isdef("__DATA18MAP") then
    window.move(window.find(WND_STAGEMAP, 25505), window.left(window.find(WND_STAGEMAP, 25505)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25505), false)
  else
    window.show(window.find(WND_STAGEMAP, 25505), false)
  end
  if game.isdef("__DATA19MAP") then
    window.move(window.find(WND_STAGEMAP, 25506), window.left(window.find(WND_STAGEMAP, 25506)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25506), false)
  else
    window.show(window.find(WND_STAGEMAP, 25506), false)
  end
  if game.isdef("__DATA20MAP") then
    window.move(window.find(WND_STAGEMAP, 25507), window.left(window.find(WND_STAGEMAP, 25507)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25507), false)
  else
    window.show(window.find(WND_STAGEMAP, 25507), false)
  end
  if game.isdef("__DATA21MAP") then
    window.move(window.find(WND_STAGEMAP, 25508), window.left(window.find(WND_STAGEMAP, 25508)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25508), false)
  else
    window.show(window.find(WND_STAGEMAP, 25508), false)
  end
  if game.isdef("__DATA22MAP") then
    window.move(window.find(WND_STAGEMAP, 25509), window.left(window.find(WND_STAGEMAP, 25509)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25509), false)
  else
    window.show(window.find(WND_STAGEMAP, 25509), false)
  end
  if game.isdef("__DATA23MAP") then
    window.move(window.find(WND_STAGEMAP, 25510), window.left(window.find(WND_STAGEMAP, 25510)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25510), false)
  else
    window.show(window.find(WND_STAGEMAP, 25510), false)
  end
  if game.isdef("__DATA24MAP") then
    window.move(window.find(WND_STAGEMAP, 25511), window.left(window.find(WND_STAGEMAP, 25511)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25511), false)
  else
    window.show(window.find(WND_STAGEMAP, 25511), false)
  end
  if game.isdef("__DATA25MAP") then
    window.move(window.find(WND_STAGEMAP, 25512), window.left(window.find(WND_STAGEMAP, 25512)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25512), false)
  else
    window.show(window.find(WND_STAGEMAP, 25512), false)
  end
  if game.isdef("__DATA26MAP") then
    window.move(window.find(WND_STAGEMAP, 25513), window.left(window.find(WND_STAGEMAP, 25513)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25513), false)
  else
    window.show(window.find(WND_STAGEMAP, 25513), false)
  end
  if game.isdef("__DATA27MAP") then
    window.move(window.find(WND_STAGEMAP, 25514), window.left(window.find(WND_STAGEMAP, 25514)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25514), false)
  else
    window.show(window.find(WND_STAGEMAP, 25514), false)
  end
  if game.isdef("__DATA28MAP") then
    window.move(window.find(WND_STAGEMAP, 25515), window.left(window.find(WND_STAGEMAP, 25515)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25515), false)
  else
    window.show(window.find(WND_STAGEMAP, 25515), false)
  end
  if game.isdef("__DATA29MAP") then
    window.move(window.find(WND_STAGEMAP, 25516), window.left(window.find(WND_STAGEMAP, 25516)), SYSTEM_SCREEN_HEIGHT - 19)
    window.show(window.find(WND_STAGEMAP, 25516), false)
  else
    window.show(window.find(WND_STAGEMAP, 25516), false)
  end
  game.openmap(1, WND_STAGEMAP)
  window.regsetting(WND_STAGEMAP, "WND_STAGEMAP")
  return 1
end

function OnChangeMap(dwID, dwCmdID, dwParam, pParam)
  local MapPage = 1
  local MaxMapPage = MAX_MAPPAGE
  if game.isdef("__USA") then
    MaxMapPage = MaxMapPage + 2
  end
  APPDATA_CHANGE_MAP = APPDATA_CHANGE_MAP + 1
  if MaxMapPage < APPDATA_CHANGE_MAP then
    APPDATA_CHANGE_MAP = 1
  end
  window.trace("MapPage:" .. APPDATA_CHANGE_MAP)
  if game.isdef("__DATA1") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12899))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12899), true)
    else
      window.show(window.find(WND_STAGEMAP, 12899), false)
    end
  end
  if game.isdef("__DATA2MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12898))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12898), true)
    else
      window.show(window.find(WND_STAGEMAP, 12898), false)
    end
  end
  if game.isdef("__DATA3MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12897))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12897), true)
    else
      window.show(window.find(WND_STAGEMAP, 12897), false)
    end
  end
  if game.isdef("__DATA4MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12896))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12896), true)
    else
      window.show(window.find(WND_STAGEMAP, 12896), false)
    end
  end
  if game.isdef("__DATA5MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12895))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12895), true)
    else
      window.show(window.find(WND_STAGEMAP, 12895), false)
    end
  end
  if game.isdef("__DATA6MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12894))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12894), true)
    else
      window.show(window.find(WND_STAGEMAP, 12894), false)
    end
  end
  if game.isdef("__DATA7MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12909))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12909), true)
    else
      window.show(window.find(WND_STAGEMAP, 12909), false)
    end
  end
  if game.isdef("__DATA8MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12910))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12910), true)
    else
      window.show(window.find(WND_STAGEMAP, 12910), false)
    end
  end
  if game.isdef("__DATA9MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12919))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12919), true)
    else
      window.show(window.find(WND_STAGEMAP, 12919), false)
    end
  end
  if game.isdef("__DATA10MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12928))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12928), true)
    else
      window.show(window.find(WND_STAGEMAP, 12928), false)
    end
  end
  if game.isdef("__DATA11MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 12929))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 12929), true)
    else
      window.show(window.find(WND_STAGEMAP, 12929), false)
    end
  end
  if game.isdef("__DATA12MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 24800))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 24800), true)
    else
      window.show(window.find(WND_STAGEMAP, 24800), false)
    end
  end
  if game.isdef("__DATA13MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25500))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25500), true)
    else
      window.show(window.find(WND_STAGEMAP, 25500), false)
    end
  end
  if game.isdef("__DATA14MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25501))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25501), true)
    else
      window.show(window.find(WND_STAGEMAP, 25501), false)
    end
  end
  if game.isdef("__DATA15MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25502))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25502), true)
    else
      window.show(window.find(WND_STAGEMAP, 25502), false)
    end
  end
  if game.isdef("__DATA16MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25503))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25503), true)
    else
      window.show(window.find(WND_STAGEMAP, 25503), false)
    end
  end
  if game.isdef("__DATA17MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25504))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25504), true)
    else
      window.show(window.find(WND_STAGEMAP, 25504), false)
    end
  end
  if game.isdef("__DATA18MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25505))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25505), true)
    else
      window.show(window.find(WND_STAGEMAP, 25505), false)
    end
  end
  if game.isdef("__DATA19MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25506))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25506), true)
    else
      window.show(window.find(WND_STAGEMAP, 25506), false)
    end
  end
  if game.isdef("__DATA20MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25507))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25507), true)
    else
      window.show(window.find(WND_STAGEMAP, 25507), false)
    end
  end
  if game.isdef("__DATA21MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25508))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25508), true)
    else
      window.show(window.find(WND_STAGEMAP, 25508), false)
    end
  end
  if game.isdef("__DATA22MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25509))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25509), true)
    else
      window.show(window.find(WND_STAGEMAP, 25509), false)
    end
  end
  if game.isdef("__DATA23MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25510))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25510), true)
    else
      window.show(window.find(WND_STAGEMAP, 25510), false)
    end
  end
  if game.isdef("__DATA24MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25511))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25511), true)
    else
      window.show(window.find(WND_STAGEMAP, 25511), false)
    end
  end
  if game.isdef("__DATA25MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25512))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25512), true)
    else
      window.show(window.find(WND_STAGEMAP, 25512), false)
    end
  end
  if game.isdef("__DATA26MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25513))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25513), true)
    else
      window.show(window.find(WND_STAGEMAP, 25513), false)
    end
  end
  if game.isdef("__DATA27MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25514))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25514), true)
    else
      window.show(window.find(WND_STAGEMAP, 25514), false)
    end
  end
  if game.isdef("__DATA28MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25515))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25515), true)
    else
      window.show(window.find(WND_STAGEMAP, 25515), false)
    end
  end
  if game.isdef("__DATA29MAP") then
    MapPage = window.getappdata(window.find(WND_STAGEMAP, 25516))
    if MapPage == APPDATA_CHANGE_MAP then
      window.show(window.find(WND_STAGEMAP, 25516), true)
    else
      window.show(window.find(WND_STAGEMAP, 25516), false)
    end
  end
  return 1
end

function OnCheckNpcName(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    game.showmapname(1)
  else
    game.showmapname(0)
  end
  return 1
end

function OnCheckGuildName(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    game.showguildname(1)
    game.showplacename(0)
    window.setcheck(window.find(WND_STAGEMAP, 12248), false)
  else
    game.showguildname(0)
  end
  return 1
end

function OnCheckPlaceName(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) == true then
    game.showplacename(1)
    game.showguildname(0)
    window.setcheck(window.find(WND_STAGEMAP, 12247), false)
  else
    game.showplacename(0)
  end
  return 1
end

function OnCloseStageMapWnd()
  if window.isexist(WND_STAGEMAP) then
    game.setstagerender(1)
    game.findnpc(0)
    window.destroy(WND_STAGEMAP)
    WND_STAGEMAP = 0
    game.setrobotvar_bool(AF_BOL_ISSHOWAREA, false)
    game.setrobotvar_bool(DATAID_AUTO_GATHER_ISSHOWAREA, false)
  end
  return 1
end

function OnStageMapPage(dwID, dwCmdID, dwParam, pParam)
  if dwID == window.find(WND_STAGEMAP, 12245) then
    game.setstagemappage(0)
    window.show(window.find(WND_STAGEMAP, 558), true)
    window.show(window.find(WND_STAGEMAP, 12247), false)
    window.show(window.find(WND_STAGEMAP, 12248), false)
  elseif dwID == window.find(WND_STAGEMAP, 12246) then
    game.setstagemappage(1)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12899) then
    game.setstagemappage(2)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12898) then
    game.setstagemappage(3)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12897) then
    game.setstagemappage(4)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12896) then
    game.setstagemappage(5)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12895) then
    game.setstagemappage(6)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12894) then
    game.setstagemappage(7)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12909) then
    game.setstagemappage(8)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12910) then
    game.setstagemappage(9)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12919) then
    game.setstagemappage(10)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12928) then
    game.setstagemappage(11)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 12929) then
    game.setstagemappage(12)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 24800) then
    game.setstagemappage(13)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25500) then
    game.setstagemappage(14)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25501) then
    game.setstagemappage(15)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25502) then
    game.setstagemappage(16)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25503) then
    game.setstagemappage(17)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25504) then
    game.setstagemappage(18)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25505) then
    game.setstagemappage(19)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25506) then
    game.setstagemappage(20)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25507) then
    game.setstagemappage(21)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25508) then
    game.setstagemappage(22)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25509) then
    game.setstagemappage(23)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25510) then
    game.setstagemappage(24)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25511) then
    game.setstagemappage(25)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25512) then
    game.setstagemappage(26)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25513) then
    game.setstagemappage(27)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25514) then
    game.setstagemappage(28)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25515) then
    game.setstagemappage(29)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  elseif dwID == window.find(WND_STAGEMAP, 25516) then
    game.setstagemappage(30)
    window.show(window.find(WND_STAGEMAP, 558), false)
    window.show(window.find(WND_STAGEMAP, 12247), true)
    window.show(window.find(WND_STAGEMAP, 12248), true)
  end
  return 1
end

function ResetChatWnd()
  window.move(WND_CHAT, 0, SYSTEM_SCREEN_HEIGHT - window.height(WND_CHAT) - 6)
  WND_COMMAND_X = SYSTEM_SCREEN_WIDTH - window.width(WND_COMMAND) - 4
  WND_COMMAND_Y = SYSTEM_SCREEN_HEIGHT - 6
  OnLoadCommand(true)
  window.setclipping(WND_COMMAND, 0, 0, SYSTEM_SCREEN_WIDTH, SYSTEM_SCREEN_HEIGHT)
  window.move(WND_COMMAND, WND_COMMAND_X, WND_COMMAND_Y)
  if game.isdef("PS3") == true then
    WND_MINIMAP_X = SYSTEM_SCREEN_WIDTH - window.width(WND_MINIMAP)
    WND_MINIMAP_Y = 0
    window.move(WND_MINIMAP, WND_MINIMAP_X, WND_MINIMAP_Y)
  end
  return 1
end
