SysChangePage = 0
MusicVolume = 100
SoundVolume = 100
VoiceVolume = 100
CharSound = true
MonsSound = true
EmotSound = true
GameWndSizeWidth = SYSTEM_SCREEN_WIDTH
GameWndSizeHeight = SYSTEM_SCREEN_HEIGHT
GameWndFullScreen = false
ShowWndMix = 0
ShowWeather = 0
ShowShadow = 0
ShowShop = 0
DollEffect = 0
SkillEffect = 0
ShowNoHeadEQ = false
ShowEarthquake = true
SpeechBubbleEffect = 0
ShowObjMsg = true
ShowCharExpMsg = true
ShowSkillExpMsg = true
ShowHelp = true
ShowCharInfo = false
ShowCharImage = 0
ShowCharWords = 0
NoTrade = false
NoFriend = false
NoGroup = false
NoEqCrown = false
NoGuild = false
NoGame = false
NoAnonymous = false
NoShareCardBook = false
NoEquipView = false
MouseReverse = false
SetSysTheme = 0
SysOKButton = false
ResetSetting = false
SetLanguage = 0
UseBigFont = true
WND_SYSTEM = 0
WND_SYSTEM_X = -1
WND_SYSTEM_Y = -1
NowSubset = 0
SwitchSubset = 0
DEFAULT_SLIDER_PARTITIONS = 10
DefaultMusicVolume = 100
DefaultSoundVolume = 100
DefaultVoiceVolume = 100
DefaultCharSound = true
DefaultMonsSound = true
DefaultEmotSound = true
DefaultShowWndMix = 0
DefaultShowWeather = 0
DefaultShowShadow = 0
DefaultShowShop = 0
DefaultDollEffect = 0
DefaultSkillEffect = 0
DefaultShowNoHeadEQ = false
DefaultShowEarthquake = true
DefaultSpeechBubbleEffect = 0
DefaultShowObjMsg = true
DefaultShowCharExpMsg = true
DefaultShowSkillExpMsg = true
DefaultShowHelp = true
DefaultShowCharInfo = false
DefaultShowCharImage = 0
DefaultShowCharWords = 0
DefaultNoTrade = false
DefaultNoFriend = false
DefaultNoGroup = false
DefaultNoEqCrown = false
DefaultNoGuild = false
DefaultNoGame = false
DefaultNoAnonymous = false
DefaultNoShareCardBook = false
DefaultNoEquipView = false
DefaultMouseReverse = false
DefaultSetSysTheme = 0
DefaultUseBigFont = true
MusicVolumeTemp = 100
SoundVolumeTemp = 100
VoiceVolumeTemp = 100
CharSoundTemp = true
MonsSoundTemp = true
EmotSoundTemp = true
GameWndSizeWidthTemp = SYSTEM_SCREEN_WIDTH
GameWndSizeHeightTemp = SYSTEM_SCREEN_HEIGHT
GameWndFullScreenTemp = false
ShowWndMixTemp = 0
ShowWeatherTemp = 0
ShowShadowTemp = 0
ShowShopTemp = 0
DollEffectTemp = 0
SkillEffectTemp = 0
ShowNoHeadEQTemp = false
ShowEarthquakeTemp = true
SpeechBubbleEffectTemp = 0
ShowObjMsgTemp = true
ShowCharExpMsgTemp = true
ShowSkillExpMsgTemp = true
ShowHelpTemp = true
ShowCharInfoTemp = false
ShowCharImageTemp = 0
ShowCharWordsTemp = 0
NoTradeTemp = false
NoFriendTemp = false
NoGroupTemp = false
NoEqCrownTemp = false
NoGuildTemp = false
NoGameTemp = false
NoAnonymousTemp = false
NoShareCardBookTemp = false
NoEquipViewTemp = false
MouseReverseTemp = false
SetSysThemeTemp = 0
IsSysChange = false
SetLanguageTemp = 0
UseBigFontTemp = true

function CreateSystemWnd()
  if window.isexist(WND_SYSTEM) then
    window.destroy(WND_SYSTEM)
    WND_SYSTEM = 0
    return
  end
  WND_SYSTEM = window.create(12002, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_SYSTEM_X or 0 > WND_SYSTEM_Y then
    window.move(WND_SYSTEM, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_SYSTEM, WND_SYSTEM_X, WND_SYSTEM_Y)
  end
  window.regsetting(WND_SYSTEM, "WND_SYSTEM")
  local Wnd_hd, Wnd_subset
  if not game.isdef("__JAPAN") then
    Wnd_hd = window.create(12129, WND_SYSTEM, 0, SYSTEM_HANDLER)
    if game.issafeverifyset() then
      Wnd_hd = window.create(12249, WND_SYSTEM, 0, 0)
    end
  end
  if game.isdef("__ANTIPLAY") then
    Wnd_hd = window.create(12262, WND_SYSTEM, 0, SYSTEM_HANDLER)
    window.moveoffset(window.find(WND_SYSTEM, 12129), 31, 0)
    if game.issafeverifyset() then
      window.moveoffset(window.find(WND_SYSTEM, 12249), 31, 0)
    end
  end
  BackupSetting()
  SysOKButton = false
  ResetSetting = false
  Wnd_hd = window.find(WND_SYSTEM, 12003)
  window.setradio(Wnd_hd, SysChangePage)
  SetPageOne()
  SetPageTwo()
  Wnd_hd = window.find(WND_SYSTEM, 12034)
  GameWndSizeWidthTemp = GameWndSizeWidth
  GameWndSizeHeightTemp = GameWndSizeHeight
  window.settitle(Wnd_hd, GameWndSizeWidthTemp .. " X " .. GameWndSizeHeightTemp)
  SetPageThree()
  local page = window.find(WND_SYSTEM, 12031)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(WND_SYSTEM, 12081)
  if page ~= 0 then
    window.show(page, false)
  end
  if game.isvlogin() then
    window.enable(window.find(WND_SYSTEM, 12007), false)
  end
  if game.isdef("PS3") == true then
    window.create(10127, WND_SYSTEM, 0, SYSTEM_HANDLER)
  end
  return 1
end

function SetPageOne()
  local Wnd_hd = 0
  for n = 12018, 12020 do
    Wnd_hd = window.find(WND_SYSTEM, n)
    window.setrange(Wnd_hd, 0, DEFAULT_SLIDER_PARTITIONS)
    if n == 12018 then
      window.setpos(Wnd_hd, MusicVolume / DEFAULT_SLIDER_PARTITIONS)
    elseif n == 12019 then
      window.setpos(Wnd_hd, SoundVolume / DEFAULT_SLIDER_PARTITIONS)
    else
      window.setpos(Wnd_hd, VoiceVolume / DEFAULT_SLIDER_PARTITIONS)
    end
  end
  Wnd_hd = window.find(WND_SYSTEM, 12021)
  window.setcheck(Wnd_hd, CharSound)
  Wnd_hd = window.find(WND_SYSTEM, 12022)
  window.setcheck(Wnd_hd, MonsSound)
  Wnd_hd = window.find(WND_SYSTEM, 12023)
  window.setcheck(Wnd_hd, EmotSound)
  return 1
end

function SetPageTwo()
  local Wnd_hd = 0
  Wnd_hd = window.find(WND_SYSTEM, 12036)
  window.setcheck(Wnd_hd, not GameWndFullScreenTemp)
  Wnd_hd = window.find(WND_SYSTEM, 12064)
  window.setradio(Wnd_hd, ShowWndMix)
  Wnd_hd = window.find(WND_SYSTEM, 12040)
  window.setradio(Wnd_hd, ShowWeather)
  Wnd_hd = window.find(WND_SYSTEM, 12042)
  window.setradio(Wnd_hd, ShowShadow)
  Wnd_hd = window.find(WND_SYSTEM, 12044)
  window.setradio(Wnd_hd, ShowShop)
  Wnd_hd = window.find(WND_SYSTEM, 12047)
  window.setradio(Wnd_hd, DollEffect)
  Wnd_hd = window.find(WND_SYSTEM, 12052)
  window.setradio(Wnd_hd, SkillEffect)
  Wnd_hd = window.find(WND_SYSTEM, 12060)
  window.setradio(Wnd_hd, SpeechBubbleEffect)
  Wnd_hd = window.find(WND_SYSTEM, 12050)
  window.setcheck(Wnd_hd, ShowNoHeadEQ)
  Wnd_hd = window.find(WND_SYSTEM, 12055)
  window.setcheck(Wnd_hd, ShowEarthquake)
  Wnd_hd = window.find(WND_SYSTEM, 12067)
  window.setcheck(Wnd_hd, ShowObjMsg)
  Wnd_hd = window.find(WND_SYSTEM, 12068)
  window.setcheck(Wnd_hd, ShowCharExpMsg)
  Wnd_hd = window.find(WND_SYSTEM, 12069)
  window.setcheck(Wnd_hd, ShowSkillExpMsg)
  if game.isdef("PS3") == true then
    Wnd_hd = window.find(WND_SYSTEM, 12032)
    window.show(Wnd_hd, false)
    Wnd_hd = window.find(WND_SYSTEM, 12034)
    window.show(Wnd_hd, false)
    Wnd_hd = window.find(WND_SYSTEM, 12035)
    window.show(Wnd_hd, false)
    Wnd_hd = window.find(WND_SYSTEM, 12036)
    window.show(Wnd_hd, false)
    local page2 = window.find(WND_SYSTEM, 12031)
    window.create(10114, page2, 0, SYSTEM_HANDLER)
    window.create(10115, page2, 0, SYSTEM_HANDLER)
  end
  if game.isdef("__MULTI_LANG") == true then
    Wnd_hd = window.find(WND_SYSTEM, 10117)
    if Wnd_hd == 0 then
      local page2 = window.find(WND_SYSTEM, 12031)
      window.create(10119, page2, 0, SYSTEM_HANDLER)
      window.create(10118, page2, 0, SYSTEM_HANDLER)
      window.create(10117, page2, 0, SYSTEM_HANDLER)
      window.create(10116, page2, 0, SYSTEM_HANDLER)
    end
    Wnd_hd = window.find(WND_SYSTEM, 10117)
    window.setradio(Wnd_hd, SetLanguage)
  end
  if game.isdef("PS3") == true then
    Wnd_hd = window.find(WND_SYSTEM, 10134)
    if Wnd_hd == 0 then
      local page2 = window.find(WND_SYSTEM, 12031)
      Wnd_hd = window.create(10134, page2, 0, SYSTEM_HANDLER)
    end
    window.setcheck(Wnd_hd, UseBigFont)
  end
  return 1
end

function ResetFullScreenType()
  local Wnd_hd = 0
  Wnd_hd = window.find(WND_SYSTEM, 12036)
  window.setcheck(Wnd_hd, not GameWndFullScreenTemp)
  return 1
end

function SetPageThree()
  local Wnd_hd = 0
  Wnd_hd = window.find(WND_SYSTEM, 12083)
  window.setcheck(Wnd_hd, ShowCharInfo)
  Wnd_hd = window.find(WND_SYSTEM, 12086)
  window.setradio(Wnd_hd, ShowCharImage)
  Wnd_hd = window.find(WND_SYSTEM, 12089)
  window.setradio(Wnd_hd, ShowCharWords)
  Wnd_hd = window.find(WND_SYSTEM, 12092)
  window.setcheck(Wnd_hd, NoTradeTemp)
  Wnd_hd = window.find(WND_SYSTEM, 12093)
  window.setcheck(Wnd_hd, NoFriendTemp)
  Wnd_hd = window.find(WND_SYSTEM, 12094)
  window.setcheck(Wnd_hd, NoGroupTemp)
  Wnd_hd = window.find(WND_SYSTEM, 28145)
  window.setcheck(Wnd_hd, NoEqCrownTemp)
  if game.isdef("__ACHIEVEMENT") then
    window.show(Wnd_hd, true)
  else
    window.show(Wnd_hd, false)
  end
  Wnd_hd = window.find(WND_SYSTEM, 12095)
  window.setcheck(Wnd_hd, NoGuildTemp)
  Wnd_hd = window.find(WND_SYSTEM, 12103)
  window.setcheck(Wnd_hd, NoGameTemp)
  Wnd_hd = window.find(WND_SYSTEM, 12104)
  window.setcheck(Wnd_hd, NoAnonymous)
  if game.isdef("__HITPARADE_ANONYMOUS") then
    window.show(Wnd_hd, true)
  else
    window.show(Wnd_hd, false)
  end
  Wnd_hd = window.find(WND_SYSTEM, 12105)
  window.setcheck(Wnd_hd, NoShareCardBook)
  if game.isdef("__CARD") then
    window.show(Wnd_hd, true)
    if game.isdef("__HITPARADE_ANONYMOUS") == false then
      window.move(Wnd_hd, window.left(WND_SYSTEM) + 14, window.top(WND_SYSTEM) + 158)
    end
  else
    window.show(Wnd_hd, false)
  end
  Wnd_hd = window.find(WND_SYSTEM, 12106)
  window.setcheck(Wnd_hd, NoEquipView)
  if game.isdef("__EQUIPVIEW") then
    window.show(Wnd_hd, true)
  else
    window.show(Wnd_hd, false)
  end
  Wnd_hd = window.find(WND_SYSTEM, 12107)
  window.setcheck(Wnd_hd, MouseReverse)
  if game.isdef("__MOUSE_REVERSE") then
    window.show(Wnd_hd, true)
  else
    window.show(Wnd_hd, false)
  end
  Wnd_hd = window.find(WND_SYSTEM, 12097)
  window.setradio(Wnd_hd, SetSysTheme)
  game.loadtheme(SetSysTheme + 1)
  return 1
end

function SaveState_CheckButton(dwID, dwCmdID, dwParam, pParam)
  local Wnd_n = window.parent(dwID)
  local Wnd = window.parent(Wnd_n)
  local temp = window.ischeck(dwID)
  if dwID == window.find(Wnd, 12021) then
    CharSound = temp
  elseif dwID == window.find(Wnd, 12022) then
    MonsSound = temp
  elseif dwID == window.find(Wnd, 12023) then
    EmotSound = temp
  elseif dwID == window.find(Wnd, 12036) then
    GameWndFullScreen = not temp
  elseif dwID == window.find(Wnd, 12050) then
    ShowNoHeadEQ = temp
    game.dollheadswitch(not temp)
  elseif dwID == window.find(Wnd, 12055) then
    ShowEarthquake = temp
  elseif dwID == window.find(Wnd, 12067) then
    ShowObjMsg = temp
  elseif dwID == window.find(Wnd, 12068) then
    ShowCharExpMsg = temp
  elseif dwID == window.find(Wnd, 12069) then
    ShowSkillExpMsg = temp
  elseif dwID == window.find(Wnd, 10134) then
    UseBigFont = temp
    game.changefontsize(temp)
  elseif dwID == window.find(Wnd, 12083) then
    ShowCharInfo = temp
    game.showallinfo(temp)
  elseif dwID == window.find(Wnd, 12092) then
    NoTradeTemp = temp
  elseif dwID == window.find(Wnd, 12093) then
    NoFriendTemp = temp
  elseif dwID == window.find(Wnd, 12094) then
    NoGroupTemp = temp
  elseif dwID == window.find(Wnd, 28145) then
    NoEqCrownTemp = temp
    if game.isdef("__ACHIEVEMENT") then
      game.noeqcrown(temp)
    end
  elseif dwID == window.find(Wnd, 12095) then
    NoGuildTemp = temp
  elseif dwID == window.find(Wnd, 12103) then
    NoGameTemp = temp
  elseif dwID == window.find(Wnd, 12104) then
    NoAnonymousTemp = temp
  elseif dwID == window.find(Wnd, 12105) then
    NoShareCardBookTemp = temp
  elseif dwID == window.find(Wnd, 12106) then
    NoEquipViewTemp = temp
  elseif dwID == window.find(Wnd, 12107) then
    MouseReverseTemp = temp
  end
  IsSysChange = true
  return 1
end

function SaveState_RadioButton(dwID, dwCmdID, dwParam, pParam)
  local appdata = window.getappdata(dwID)
  local temp = window.getradio(dwID)
  if appdata == 12064 or appdata == 12065 then
    ShowWndMix = temp
  elseif appdata == 12040 or appdata == 12041 then
    ShowWeather = temp
    game.setgametime()
  elseif appdata == 12042 or appdata == 12043 then
    ShowShadow = temp
    game.setshowshadow(ShowShadow)
  elseif appdata == 12044 or appdata == 12045 then
    ShowShop = temp
  elseif appdata == 12047 or appdata == 12048 or appdata == 12049 then
    DollEffect = temp
    game.dollswitch(DollEffect)
  elseif appdata == 12052 or appdata == 12053 or appdata == 12054 then
    SkillEffect = temp
  elseif appdata == 12060 or appdata == 12061 or appdata == 12062 then
    SpeechBubbleEffect = temp
  elseif appdata == 12086 or appdata == 12087 or appdata == 12088 then
    ShowCharImage = temp
    game.showallinfo(ShowCharInfo)
  elseif appdata == 12089 or appdata == 12090 or appdata == 12091 then
    ShowCharWords = temp
    game.showallinfo(ShowCharInfo)
  elseif appdata == 12097 or appdata == 12098 or appdata == 12099 or appdata == 12100 then
    SetSysTheme = temp
    game.loadtheme(SetSysTheme + 1)
  elseif appdata == 10117 or appdata == 10118 then
    SetLanguage = temp
    window.msgbox(2530, 0, 0, 0)
  end
  IsSysChange = true
  return 1
end

function Setting_ChangePage(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local appdata = window.getappdata(dwID)
  local page = window.find(Wnd, 12011)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 12031)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, 12081)
  if page ~= 0 then
    window.show(page, false)
  end
  page = window.find(Wnd, appdata)
  window.show(page, true)
  return 1
end

function PopListDown(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12035, Wnd, 0, 0)
  if Wnd_hd ~= nil then
    window.insertitemstrappnum(Wnd_hd, " 800 X 600", 0, 0)
    window.insertitemstrappnum(Wnd_hd, " 1024 X 768", 0, 1)
    if game.isdef("__WIDE_SCREEN") then
      if system.issupportvideomode(1280, 768) then
        window.insertitemstrappnum(Wnd_hd, " 1280 X 768", 0, 2)
      end
      if system.issupportvideomode(1280, 800) then
        window.insertitemstrappnum(Wnd_hd, " 1280 X 800", 0, 3)
      end
    end
  end
  return 1
end

function Change_Music_Volume(dwID, dwCmdID, dwParam, pParam)
  local a = window.parent(dwID)
  local Wnd = window.parent(a)
  local Volume = window.getpos(dwID)
  MusicVolume = (DXSOUND_VOLUME_MAX - DXSOUND_VOLUME_MIN) / DEFAULT_SLIDER_PARTITIONS * Volume
  system.setmusicvolume(MusicVolume)
  IsSysChange = true
  return 1
end

function Change_Sound_Volume(dwID, dwCmdID, dwParam, pParam)
  local a = window.parent(dwID)
  local Wnd = window.parent(a)
  local Volume = window.getpos(dwID)
  SoundVolume = (DXSOUND_VOLUME_MAX - DXSOUND_VOLUME_MIN) / DEFAULT_SLIDER_PARTITIONS * Volume
  system.setsoundvolume(SoundVolume)
  IsSysChange = true
  return 1
end

function Change_Voice_Volume(dwID, dwCmdID, dwParam, pParam)
  local a = window.parent(dwID)
  local Wnd = window.parent(a)
  local Volume = window.getpos(dwID)
  VoiceVolume = (DXSOUND_VOLUME_MAX - DXSOUND_VOLUME_MIN) / DEFAULT_SLIDER_PARTITIONS * Volume
  system.setvoicevolume(VoiceVolume)
  IsSysChange = true
  return 1
end

function ChangeWndSize(dwID, dwCmdID, dwParam, pParam)
  local Wnd_hd = window.parent(dwID)
  local dwSelect = window.getitemappdata(dwID, dwParam)
  if dwSelect == 0 then
    GameWndSizeWidthTemp = 800
    GameWndSizeHeightTemp = 600
  elseif dwSelect == 1 then
    GameWndSizeWidthTemp = 1024
    GameWndSizeHeightTemp = 768
  end
  if game.isdef("__WIDE_SCREEN") then
    if dwSelect == 2 then
      GameWndSizeWidthTemp = 1280
      GameWndSizeHeightTemp = 768
    elseif dwSelect == 3 then
      GameWndSizeWidthTemp = 1280
      GameWndSizeHeightTemp = 800
    end
  end
  local Sta = window.find(Wnd_hd, 12034)
  if Sta ~= 0 then
    window.settitle(Sta, GameWndSizeWidthTemp .. " X " .. GameWndSizeHeightTemp)
  end
  window.destroy(dwID)
  IsSysChange = true
  return 1
end

function RestoreSetting(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.find(Wnd, 12003)
  local page = window.getradio(Wnd_hd)
  if page == 0 then
    MusicVolume = DefaultMusicVolume
    SoundVolume = DefaultSoundVolume
    VoiceVolume = DefaultVoiceVolume
    CharSound = DefaultCharSound
    MonsSound = DefaultMonsSound
    EmotSound = DefaultEmotSound
    SetPageOne()
    system.setmusicvolume(MusicVolume)
    system.setsoundvolume(SoundVolume)
    system.setvoicevolume(VoiceVolume)
  elseif page == 1 then
    ShowWndMix = DefaultShowWndMix
    ShowWeather = DefaultShowWeather
    ShowShadow = DefaultShowShadow
    ShowShop = DefaultShowShop
    DollEffect = DefaultDollEffect
    SkillEffect = DefaultSkillEffect
    ShowNoHeadEQ = DefaultShowNoHeadEQ
    ShowEarthquake = DefaultShowEarthquake
    SpeechBubbleEffect = DefaultSpeechBubbleEffect
    ShowObjMsg = DefaultShowObjMsg
    ShowCharExpMs = DefaultShowCharExpMsg
    ShowSkillExpMsg = DefaultShowSkillExpMsg
    ShowHelp = DefaultShowHelp
    local old = UseBigFont
    UseBigFont = DefaultUseBigFont
    SetPageTwo()
    game.dollheadswitch(not ShowNoHeadEQ)
    if old ~= UseBigFont then
      game.changefontsize(UseBigFont)
    end
    game.setshowshadow(ShowShadow)
  elseif page == 2 then
    if game.isdef("__MALAYSIA") or game.isdef("__KOREA") then
      ShowCharInfo = true
      ShowCharImage = 1
    else
      ShowCharInfo = DefaultShowCharInfo
      ShowCharImage = DefaultShowCharImage
    end
    game.showallinfo(ShowCharInfo)
    if game.isdef("__ACHIEVEMENT") then
      NoEqCrownTemp = DefaultNoEqCrown
      game.noeqcrown(DefaultNoEqCrown)
    end
    ShowCharWords = DefaultShowCharWords
    NoTradeTemp = DefaultNoTrade
    NoFriendTemp = DefaultNoFriend
    NoGroupTemp = DefaultNoGroup
    NoGuildTemp = DefaultNoGuild
    NoGameTemp = DefaultNoGame
    NoAnonymousTemp = DefaultNoAnonymous
    NoShareCardBookTemp = DefaultNoShareCardBook
    NoEquipViewTemp = DefaultNoEquipView
    MouseReverse = DefaultMouseReverse
    MouseReverseTemp = DefaultMouseReverse
    SetSysTheme = DefaultSetSysTheme
    SetPageThree()
  end
  IsSysChange = true
  return 1
end

function OnSysChangeOK(dwID, dwCmdID, dwParam, pParam)
  local Wnd_hd = window.parent(dwID)
  SysOKButton = true
  if GameWndSizeWidth ~= GameWndSizeWidthTemp or GameWndSizeHeight ~= GameWndSizeHeightTemp then
    SaveQuickStyle()
    window.savesetting(GameWndSizeWidth, GameWndSizeHeight)
    GameWndSizeWidth = GameWndSizeWidthTemp
    GameWndSizeHeight = GameWndSizeHeightTemp
    SYSTEM_SCREEN_WIDTH = GameWndSizeWidth
    SYSTEM_SCREEN_HEIGHT = GameWndSizeHeight
    system.changeresolution(GameWndSizeWidth, GameWndSizeHeight)
    UpdateCharInfoWnd()
    SetQuickStyle()
    ResetChatWnd()
  end
  if GameWndFullScreen ~= GameWndFullScreenTemp then
    system.switchscreen()
  end
  if ShowHelp then
    game.settipshow(1)
  else
    game.settipshow(0)
  end
  TuitionResetTips()
  NoTrade = NoTradeTemp
  NoFriend = NoFriendTemp
  NoGroup = NoGroupTemp
  NoEqCrown = NoEqCrownTemp
  NoGuild = NoGuildTemp
  NoGame = NoGameTemp
  NoAnonymous = NoAnonymousTemp
  NoShareCardBook = NoShareCardBookTemp
  NoEquipView = NoEquipViewTemp
  MouseReverse = MouseReverseTemp
  if game.isdef("__HITPARADE_ANONYMOUS") then
    if NoAnonymous then
      game.netcommand(31, 1)
    else
      game.netcommand(31, 0)
    end
  end
  if game.isdef("__CARD") then
    if NoShareCardBook then
      game.netcommand(33, 1)
    else
      game.netcommand(33, 0)
    end
  end
  if game.isdef("__EQUIPVIEW") then
    if NoEquipView then
      game.netcommand(39, 1)
    else
      game.netcommand(39, 0)
    end
  end
  if dwID == window.find(window.parent(window.parent(dwID)), 12223) then
    window.destroy(window.parent(window.parent(dwID)))
  else
    window.destroy(window.parent(dwID))
  end
  if game.isdef("__MODIFY_SAVESETTING") then
    game.savesetting()
  end
  if game.isdef("__ACHIEVEMENT") then
    game.noeqcrown(NoEqCrown)
  end
  return 1
end

function OnSysChangeCancel(dwID, dwCmdID, dwParam, pParam)
  if IsSysChange then
    local Wnd_hd = window.create(12221, WND_SYSTEM, 0, 0)
  else
    window.destroy(window.parent(dwID))
  end
  return 1
end

function OnSysChangeCancel_X(dwID, dwCmdID, dwParam, pParam)
  if IsSysChange then
    local Wnd_hd = window.create(12221, WND_SYSTEM, 0, 0)
    return 0
  else
    window.destroy(window.parent(dwID))
    return 1
  end
end

function OnSysCancelNoSave(dwID, dwCmdID, dwParam, pParam)
  if not SysOKButton then
    GetBackupSetting()
    NoTradeTemp = NoTrade
    NoFriendTemp = NoFriend
    NoGroupTemp = NoGroup
    NoEqCrownTemp = NoEqCrown
    NoGuildTemp = NoGuild
    NoGameTemp = NoGame
    NoAnonymousTemp = NoAnonymous
    NoSharCardBookTemp = NoSharCardBook
    NoEquipViewTemp = NoEquipView
    MouseReverseTemp = MouseReverse
    system.setmusicvolume(MusicVolume)
    system.setsoundvolume(SoundVolume)
    system.setvoicevolume(VoiceVolume)
    game.setshowshadow(ShowShadow)
    game.setgametime()
    game.showallinfo(ShowCharInfo)
    if game.isdef("__ACHIEVEMENT") then
      game.noeqcrown(NoEqCrown)
    end
    game.dollheadswitch(not ShowNoHeadEQ)
    game.dollswitch(DollEffect)
    game.loadtheme(SetSysTheme + 1)
    game.changefontsize(UseBigFont)
    if ResetSetting then
      window.restoresetting()
    end
    UpdateCharInfoWnd()
    SetQuickStyle()
  end
  local w = window.parent(window.parent(dwID))
  window.destroy(window.parent(dwID))
  window.destroy(w)
  return 1
end

function BackupSetting()
  IsSysChange = false
  MusicVolumeTemp = MusicVolume
  SoundVolumeTemp = SoundVolume
  VoiceVolumeTemp = VoiceVolume
  CharSoundTemp = CharSound
  MonsSoundTemp = MonsSound
  EmotSoundTemp = EmotSound
  GameWndFullScreenTemp = system.isfullscreen()
  ShowWndMixTemp = ShowWndMix
  ShowWeatherTemp = ShowWeather
  ShowShadowTemp = ShowShadow
  ShowShopTemp = ShowShop
  DollEffectTemp = DollEffect
  SkillEffectTemp = SkillEffect
  ShowNoHeadEQTemp = ShowNoHeadEQ
  ShowEarthquakeTemp = ShowEarthquake
  SpeechBubbleEffectTemp = SpeechBubbleEffect
  ShowObjMsgTemp = ShowObjMsg
  ShowCharExpMsgTemp = ShowCharExpMsg
  ShowSkillExpMsgTemp = ShowSkillExpMsg
  local b = game.gettipshow()
  if b then
    ShowHelp = true
  else
    ShowHelp = false
  end
  ShowHelpTemp = ShowHelp
  SetLanguageTemp = SetLanguage
  UseBigFontTemp = UseBigFont
  ShowCharInfoTemp = ShowCharInfo
  ShowCharImageTemp = ShowCharImage
  ShowCharWordsTemp = ShowCharWords
  NoTradeTemp = NoTrade
  NoFriendTemp = NoFriend
  NoGroupTemp = NoGroup
  NoEqCrownTemp = NoEqCrown
  NoGuildTemp = NoGuild
  NoGameTemp = NoGame
  NoAnonymousTemp = NoAnonymous
  NoShareCardBookTemp = NoShareCardBook
  NoEquipViewTemp = NoEquipView
  MouseReverseTemp = MouseReverse
  SetSysThemeTemp = SetSysTheme
  return 1
end

function GetBackupSetting()
  MusicVolume = MusicVolumeTemp
  SoundVolume = SoundVolumeTemp
  VoiceVolume = VoiceVolumeTemp
  CharSound = CharSoundTemp
  MonsSound = MonsSoundTemp
  EmotSound = EmotSoundTemp
  GameWndFullScreen = GameWndFullScreenTemp
  ShowWndMix = ShowWndMixTemp
  ShowWeather = ShowWeatherTemp
  ShowShadow = ShowShadowTemp
  ShowShop = ShowShopTemp
  DollEffect = DollEffectTemp
  SkillEffect = SkillEffectTemp
  ShowNoHeadEQ = ShowNoHeadEQTemp
  ShowEarthquake = ShowEarthquakeTemp
  SpeechBubbleEffect = SpeechBubbleEffectTemp
  ShowObjMsg = ShowObjMsgTemp
  ShowCharExpMsg = ShowCharExpMsgTemp
  ShowSkillExpMsg = ShowSkillExpMsgTemp
  ShowHelp = ShowHelpTemp
  SetLanguage = SetLanguageTemp
  UseBigFont = UseBigFontTemp
  ShowCharInfo = ShowCharInfoTemp
  ShowCharImage = ShowCharImageTemp
  ShowCharWords = ShowCharWordsTemp
  SetSysTheme = SetSysThemeTemp
  return 1
end

function PopQuitWnd(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12121, Wnd, 0, 0)
  return 1
end

function OnSysQuitGame(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.logout()
  return 1
end

function PopChangeCharWnd(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12124, Wnd, 0, 0)
  return 1
end

function OnSysChangeCharGame(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.autorelogingame()
  return 1
end

function Reset_WndSetting(dwID, dwCmdID, dwParam, pParam)
  if not ResetSetting then
    SaveQuickStyle()
    window.backupsetting()
  end
  window.resetsetting()
  UpdateCharInfoWnd()
  SetQuickStyle()
  ResetSetting = true
  IsSysChange = true
  return 1
end

function OnChangeSafeVerifyPwd(dwID, dwCmdID, dwParam, pParam)
  game.changesafeverifypwd()
  return 1
end

function OnDeleteSafeVerifyPwd(dwID, dwCmdID, dwParam, pParam)
  CreateSafeVerifyDeleteWnd()
  return 1
end

function PopChangeSubsetWnd(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12257, Wnd, 0, 0)
  return 1
end

function OnSysChangeSubset(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.changesubset()
  return 1
end

function OnAntiPlayTime(dwID, dwCmdID, dwParam, pParam)
  game.antiplaytime()
  return 1
end

function PopSwitchSubsetWnd(dwID, dwCmdID, dwParam, pParam)
  local strShunt = game.getstring(3650)
  local strShunt2 = game.getstring(3651) .. strShunt
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12291, Wnd, 0, 0)
  local dwNowsubset = game.getnowsubset() + 1
  local Sta = window.find(Wnd_hd, 12297)
  if Sta ~= 0 then
    window.settitle(Sta, strShunt2 .. dwNowsubset)
  end
  local Sta2 = window.find(Wnd_hd, 12294)
  if Sta2 ~= 0 then
    if dwNowsubset ~= 1 then
      window.settitle(Sta2, strShunt .. 1)
      SwitchSubset = 0
    elseif dwNowsubset ~= 2 then
      window.settitle(Sta2, strShunt .. 2)
      SwitchSubset = 1
    elseif dwNowsubset ~= 3 then
      window.settitle(Sta2, strShunt .. 3)
      SwitchSubset = 2
    end
  end
  return 1
end

function OnSysSwitchSubset(dwID, dwCmdID, dwParam, pParam)
  window.destroy(window.parent(dwID))
  game.switchsubset(SwitchSubset)
  return 1
end

function PopSubsetListDown(dwID, dwCmdID, dwParam, pParam)
  local strShunt = " " .. game.getstring(3650)
  local Wnd = window.parent(dwID)
  local Wnd_hd = window.create(12295, Wnd, 0, 0)
  local MaxRows = window.getlistrows(Wnd_hd)
  local RowCount = 1
  local dwNowsubset = game.getnowsubset() + 1
  if Wnd_hd ~= nil then
    if dwNowsubset ~= 1 and MaxRows > RowCount then
      window.insertitemstrappnum(Wnd_hd, strShunt .. 1, 0, 0)
      RowCount = RowCount + 1
    end
    if dwNowsubset ~= 2 and MaxRows > RowCount then
      window.insertitemstrappnum(Wnd_hd, strShunt .. 2, 0, 1)
      RowCount = RowCount + 1
    end
    if dwNowsubset ~= 3 and MaxRows > RowCount then
      window.insertitemstrappnum(Wnd_hd, strShunt .. 3, 0, 2)
      RowCount = RowCount + 1
    end
    if dwNowsubset ~= 4 and MaxRows > RowCount then
      window.insertitemstrappnum(Wnd_hd, strShunt .. 4, 0, 3)
      RowCount = RowCount + 1
    end
    if dwNowsubset ~= 5 and MaxRows > RowCount then
      window.insertitemstrappnum(Wnd_hd, strShunt .. 5, 0, 4)
      RowCount = RowCount + 1
    end
  end
  return 1
end

function OnSwitchSubset(dwID, dwCmdID, dwParam, pParam)
  local strShunt = game.getstring(3650)
  local Wnd_hd = window.parent(dwID)
  SwitchSubset = window.getitemappdata(dwID, dwParam)
  local dwSelect = SwitchSubset + 1
  local Sta = window.find(Wnd_hd, 12294)
  if Sta ~= 0 then
    window.settitle(Sta, strShunt .. dwSelect)
  end
  window.destroy(dwID)
  return 1
end
