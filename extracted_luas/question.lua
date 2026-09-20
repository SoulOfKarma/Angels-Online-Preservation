WND_QUESTION = 0
WND_QUESTION_X = 0
WND_QUESTION_Y = 0
WND_QUESTION_HELP = 0
WND_QUESTION_JOIN = 0
WND_QUESTION_JOIN_X = 0
WND_QUESTION_JOIN_Y = 0
WND_QUESTION_HELP = 0
WND_QUESTION_HELP_X = 0
WND_QUESTION_HELP_Y = 0
WND_QUESTION_RANK = 0
WND_QUESTION_RANK_X = 0
WND_QUESTION_RANK_Y = 0
WND_GOTO_QTMAP = 0
WND_GOTO_QTMAP_X = 0
WND_GOTO_QTMAP_Y = 0
GUILD_USE_BEATIFYITEM = 0
GUILD_USE_EXPBELL = 0

function CreateQuestionWnd()
  if window.isexist(WND_QUESTION) then
    window.destroy(WND_QUESTION)
    WND_QUESTION = 0
    return
  end
  WND_QUESTION = window.create(24753, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_QUESTION_X or 0 > WND_QUESTION_Y then
    window.move(WND_QUESTION, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_QUESTION, WND_QUESTION_X, WND_QUESTION_Y)
  end
  window.regsetting(WND_QUESTION, "WND_QUESTION")
  return 1
end

function OnOpenQuestionWnd()
  CreateQuestionWnd()
end

function DestroyQuestionWnd()
  window.destroy(WND_QUESTION)
  WND_QUESTION = 0
  return 1
end

function CreateQtJoinWnd()
  if window.isexist(WND_QUESTION_JOIN) then
    window.destroy(WND_QUESTION_JOIN)
    WND_QUESTION_JOIN = 0
  end
  WND_QUESTION_JOIN = window.create(24758, 0, 0, SYSTEM_HANDLER)
  window.move(WND_QUESTION_JOIN, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  GUILD_USE_BEATIFYITEM = 0
  GUILD_USE_EXPBELL = 0
  window.regsetting(WND_QUESTION_JOIN, "WND_QUESTION_JOIN")
  window.regsetting(GUILD_USE_BEATIFYITEM, "GUILD_USE_BEATIFYITEM")
  window.regsetting(GUILD_USE_EXPBELL, "GUILD_USE_EXPBELL")
  return 1
end

function DestroyQtJoinWnd()
  if window.isexist(WND_QUESTION_JOIN) then
    window.destroy(WND_QUESTION_JOIN)
    WND_DAILYEVENT = 0
  end
  return 1
end

function OnQTJoin(dwID, dwCmdID, dwParam, pParam)
  game.QTJoin()
  return 1
end

function OnQTAns1(dwID, dwCmdID, dwParam, pParam)
  game.QTEncodeAns(0)
  game.QTAns1()
  return 1
end

function OnQTAns2(dwID, dwCmdID, dwParam, pParam)
  game.QTEncodeAns(1)
  game.QTAns2()
  return 1
end

function OnQTAns3(dwID, dwCmdID, dwParam, pParam)
  game.QTEncodeAns(2)
  game.QTAns3()
  return 1
end

function OnQTAns(dwID, dwCmdID, dwParam, pParam)
  game.QTSelectAns(dwID)
  return 1
end

function OnUseHeart(dwID, dwCmdID, dwParam, pParam)
  game.UseHeart()
  return 1
end

function OnUseStar(dwID, dwCmdID, dwParam, pParam)
  game.UseStar()
  return 1
end

function OnOpenGotoQuestionWnd()
  if window.isexist(WND_GOTO_QTMAP) then
    window.destroy(WND_GOTO_QTMAP)
    WND_GOTO_QTMAP = 0
    return
  end
  WND_GOTO_QTMAP = window.create(24769, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_GOTO_QTMAP_X or 0 > WND_GOTO_QTMAP_Y then
    window.move(WND_GOTO_QTMAP, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_GOTO_QTMAP, WND_GOTO_QTMAP_X, WND_GOTO_QTMAP_Y)
  end
  window.regsetting(WND_GOTO_QTMAP, "WND_GOTO_QTMAP")
  return 1
end

function DestroyGotoQtMapWnd()
  if window.isexist(WND_GOTO_QTMAP) then
    window.destroy(WND_GOTO_QTMAP)
    WND_DAILYEVENT = 0
  end
  return 1
end

function OnGotoQtMap()
  game.gotoqtmap(dwCmdID)
  return 1
end

function OnCheckUseBeatifyItem(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    GUILD_USE_BEATIFYITEM = 1
  else
    GUILD_USE_BEATIFYITEM = 0
  end
  return 1
end

function OnCheckUseExpBell(dwID, dwCmdID, dwParam, pParam)
  if window.ischeck(dwID) then
    GUILD_USE_EXPBELL = 1
  else
    GUILD_USE_EXPBELL = 0
  end
  return 1
end

function OnQTHelp(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_QUESTION_HELP) then
    window.destroy(WND_QUESTION_HELP)
    WND_QUESTION_HELP = 0
    return
  end
  WND_QUESTION_HELP = window.create(24792, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_QUESTION_HELP_X or 0 > WND_QUESTION_HELP_Y then
    window.move(WND_QUESTION_HELP, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_QUESTION_HELP, WND_QUESTION_HELP_X, WND_QUESTION_HELP_Y)
  end
  window.regsetting(WND_QUESTION_HELP, "WND_QUESTION_HELP")
  return 1
end

function CreateQTRank(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_QUESTION_RANK) then
    window.destroy(WND_QUESTION_RANK)
    WND_QUESTION_RANK = 0
    return
  end
  WND_QUESTION_RANK = window.create(24796, 0, 0, SYSTEM_HANDLER)
  if 0 > WND_QUESTION_RANK_X or 0 > WND_QUESTION_RANK_Y then
    window.move(WND_QUESTION_RANK, SYSTEM_SCREEN_WIDTH / 2, SYSTEM_SCREEN_HEIGHT / 2 - 200)
  else
    window.move(WND_QUESTION_RANK, WND_QUESTION_RANK_X, WND_QUESTION_RANK_Y)
  end
  window.regsetting(WND_QUESTION_RANK, "WND_QUESTION_RANK")
  return 1
end
