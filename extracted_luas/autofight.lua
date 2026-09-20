AF_BOL_ISAUTOFIGHT = 1001
AF_INT_AUTOFIGHTRANGE = 1002
AF_BOL_ISRESERVESP = 1003
AF_BOL_ISRESERVEMP = 1004
AF_BOL_ISKEEPRANGEMONSTER = 1005
AF_BOL_ISATTACKTARGET = 1006
AF_BOL_ISRESTINLOWHP = 1007
AF_BOL_ISRESTINLOWMP = 1008
AF_BOL_ISTRANSHPTOSP = 1009
AF_BOL_ISMEETBOSS1 = 1010
AF_BOL_ISMEETBOSS2 = 1011
AF_BOL_ISMEETBOSS3 = 1012
AF_BOL_ISINVOKE1 = 1013
AF_BOL_ISINVOKE2 = 1014
AF_INT_RESERVESP = 1015
AF_INT_RESERVEMP = 1016
AF_INT_LOWHP = 1017
AF_INT_LOWMP = 1018
AF_INT_HIGHHP = 1019
AF_INT_SKILL1 = 1020
AF_INT_SKILL2 = 1021
AF_INT_SKILL3 = 1022
AF_STRLIST_SURROUND = 1023
AF_STRLIST_TARGET = 1024
AF_INT_ORGPOSX = 1025
AF_INT_ORGPOSY = 1026
AF_INT_BACKITEM = 1027
AF_INT_INVOKEID = 1028
AF_BOL_ISMODIFIED = 1029
AF_INT_ORGMAPID = 1030
AF_BOL_ISSHOWAREA = 1031
AF_INT_SPSKILL = 1032
AF_BOL_ISGROUPATTACK = 1033
AF_INT_NUMGROUPATTACK = 1034
AF_INT_GROUPATTACKSKILL = 1035
AF_INT_NUMSP = 1036
AF_BOL_CANCHECKSUPPLY = 1037
USEITEM_CHECKMAGICSTATUS = 1038
AF_BOL_ISMAKECLONING = 1039
AF_INT_CLONINGID = 1040
DATAID_USED_TP_ITEM = 2000
MAX_AUTOFIGHTRANGE = 100
G_BOOL_AUTOFIGHT_INITIAL = false

function CreateAutoFightWnd(WND_AUTOFIGHT)
  if G_BOOL_AUTOFIGHT_INITIAL == false then
    if game.isdef("__ANGEL_WALK") then
    else
      game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, false)
    end
    G_BOOL_AUTOFIGHT_INITIAL = true
  end
  local w = window.find(WND_AUTOFIGHT, 966)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 967)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 968)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 10045)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 10046)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 10050)
  game.assistclearmagicitem(w)
  w = window.find(WND_AUTOFIGHT, 10053)
  game.assistclearmagicitem(w)
  LoadAutoFightSetting()
  return 1
end

function LoadAutoFightSetting()
  if game.getrobotvar_bool(AF_BOL_ISMODIFIED) == false then
    game.setrobotvar_int(AF_INT_AUTOFIGHTRANGE, 20)
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS1, true)
    game.setrobotvar_int(AF_INT_LOWHP, 40)
    game.setrobotvar_int(AF_INT_LOWMP, 20)
    game.setrobotvar_int(AF_INT_NUMGROUPATTACK, 3)
  end
  game.setrobotvar_bool(AF_BOL_ISMODIFIED, true)
  LoadCheckButton(960, AF_BOL_ISAUTOFIGHT)
  LoadCheckButton(971, AF_BOL_ISRESERVESP)
  LoadCheckButton(972, AF_BOL_ISRESERVEMP)
  LoadCheckButton(973, AF_BOL_ISKEEPRANGEMONSTER)
  LoadCheckButton(974, AF_BOL_ISATTACKTARGET)
  LoadCheckButton(991, AF_BOL_ISRESTINLOWHP)
  LoadCheckButton(992, AF_BOL_ISRESTINLOWMP)
  LoadCheckButton(993, AF_BOL_ISTRANSHPTOSP)
  LoadCheckButton(995, AF_BOL_ISMEETBOSS1)
  LoadCheckButton(996, AF_BOL_ISMEETBOSS2)
  LoadCheckButton(997, AF_BOL_ISMEETBOSS3)
  LoadCheckButton(999, AF_BOL_ISINVOKE1)
  LoadCheckButton(1000, AF_BOL_ISINVOKE2)
  LoadCheckButton(998, AF_BOL_ISMAKECLONING)
  LoadCheckButton(10051, AF_BOL_ISGROUPATTACK)
  LoadEditField(962, AF_INT_AUTOFIGHTRANGE)
  LoadEditField(969, AF_INT_RESERVESP)
  LoadEditField(970, AF_INT_RESERVEMP)
  LoadEditField(988, AF_INT_LOWHP)
  LoadEditField(989, AF_INT_LOWMP)
  LoadEditField(990, AF_INT_HIGHHP)
  LoadEditField(10052, AF_INT_NUMGROUPATTACK)
  LoadEditField(981, AF_INT_NUMSP)
  LoadSkill(966, AF_INT_SKILL1)
  LoadSkill(967, AF_INT_SKILL2)
  LoadSkill(968, AF_INT_SKILL3)
  LoadSkill(10046, AF_INT_INVOKEID)
  if game.isdef("__NEW_SKILL") then
    LoadSkill(10116, AF_INT_CLONINGID)
  end
  LoadSkill(10050, AF_INT_SPSKILL)
  LoadSkill(10053, AF_INT_GROUPATTACKSKILL)
  if game.isdef("__USA") then
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWHP, false)
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWMP, false)
    window.show(window.find(WND_AUTOFIGHT, 991), false)
    window.show(window.find(WND_AUTOFIGHT, 992), false)
    window.show(window.find(WND_AUTOFIGHT, 988), false)
    window.show(window.find(WND_AUTOFIGHT, 989), false)
  end
  game.autofightloadbackitem()
  game.autofightloadinvoke()
  if game.isdef("__NEW_SKILL") then
    game.autofightloadmakecloning()
  end
  game.autofightloadtarget()
  return 1
end

function LoadCheckButton(wndID, defID)
  local w = window.find(WND_AUTOFIGHT, wndID)
  window.setcheck(w, game.getrobotvar_bool(defID))
  return 1
end

function LoadEditField(wndID, defID)
  local w = window.find(WND_AUTOFIGHT, wndID)
  window.settitleint(w, game.getrobotvar_int(defID))
  return 1
end

function LoadSkill(wndID, defID)
  game.autofightloadskill(wndID, defID)
end

function LoadSkillIcon()
  LoadSkill(966, AF_INT_SKILL1)
  LoadSkill(967, AF_INT_SKILL2)
  LoadSkill(968, AF_INT_SKILL3)
  LoadSkill(10046, AF_INT_INVOKEID)
  if game.isdef("__NEW_SKILL") then
    LoadSkill(10116, AF_INT_CLONINGID)
  end
  LoadSkill(10050, AF_INT_SPSKILL)
  LoadSkill(10053, AF_INT_GROUPATTACKSKILL)
  return 1
end

function ResetAutoFightButton()
  game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, false)
  return 1
end

function OnCheckAutoFight(dwID, dwCmdID, dwParam, pParam)
  local bIsRun = window.ischeck(dwID)
  if bIsRun == true then
    game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, true)
    if game.isdef("__ANGEL_WALK") then
    else
      game.autofightsetorgpos()
    end
    local mapid = game.getmapid()
    if game.isdef("__ANGEL_WALK") then
    else
      game.setrobotvar_int(AF_INT_ORGMAPID, mapid)
    end
    game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
    local dwAutoGatherCheckWndHD = window.find(WND_AUTOPRODUCE, DATAID_AUTO_GATHER_CHECK + PRODUCE_RES_DIFF)
    window.setcheck(dwAutoGatherCheckWndHD, false)
    game.setrobotvar_bool(DATAID_AUTO_GATHER_CHECK, false)
    local dwAutoExerciseCheckWndHD = window.find(WND_AUTOASSIST, DATAID_EXERCISE_SKILL_CHECK + ASSIST_RES_DIFF)
    window.setcheck(dwAutoExerciseCheckWndHD, false)
    game.setrobotvar_bool(DATAID_EXERCISE_SKILL_CHECK, false)
  else
    game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, false)
  end
  game.checkautofight(bIsRun)
  return 1
end

function OnEditAutoFightRange(dwID, dwCmdID, dwParam, pParam)
  local range = window.gettitleint(dwID)
  if range < MAX_AUTOFIGHTRANGE then
    game.setrobotvar_int(AF_INT_AUTOFIGHTRANGE, range)
  else
    game.setrobotvar_int(AF_INT_AUTOFIGHTRANGE, MAX_AUTOFIGHTRANGE)
    window.settitle(dwID, MAX_AUTOFIGHTRANGE)
  end
  return 1
end

function OnDropAutoFirstAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropskill(966, AF_INT_SKILL1, pParam)
  return 1
end

function OnRClickAutoFirstAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearskill(966, pParam)
  game.setrobotvar_int(AF_INT_SKILL1, 0)
  return 1
end

function OnDropAutoOftenAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropskill(967, AF_INT_SKILL2, pParam)
  return 1
end

function OnRClickAutoOftenAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearskill(967, pParam)
  game.setrobotvar_int(AF_INT_SKILL2, 0)
  return 1
end

function OnDropAutoFinalAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropskill(968, AF_INT_SKILL3, pParam)
  return 1
end

function OnRClickAutoFinalAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearskill(968, pParam)
  game.setrobotvar_int(AF_INT_SKILL3, 0)
  return 1
end

function OnCheckAutoReserveSP(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISRESERVESP) == false then
    game.setrobotvar_bool(AF_BOL_ISRESERVESP, true)
  else
    game.setrobotvar_bool(AF_BOL_ISRESERVESP, false)
  end
  return 1
end

function OnCheckAutoReserveMP(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISRESERVEMP) == false then
    game.setrobotvar_bool(AF_BOL_ISRESERVEMP, true)
  else
    game.setrobotvar_bool(AF_BOL_ISRESERVEMP, false)
  end
  return 1
end

function OnEditAutoReserveSP(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(AF_INT_RESERVESP, window.gettitleint(dwID))
  return 1
end

function OnEditAutoReserveMP(dwID, dwCmdID, dwParam, pParam)
  local mp = window.gettitleint(dwID)
  if 100 < mp then
    game.setrobotvar_int(AF_INT_RESERVEMP, 100)
    window.settitle(dwID, 100)
  elseif mp < 0 then
    game.setrobotvar_int(AF_INT_RESERVEMP, 0)
    window.settitle(dwID, 0)
  else
    game.setrobotvar_int(AF_INT_RESERVEMP, mp)
  end
  return 1
end

function OnCheckAutoKeepRange(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISKEEPRANGEMONSTER) == false then
    game.setrobotvar_bool(AF_BOL_ISKEEPRANGEMONSTER, true)
  else
    game.setrobotvar_bool(AF_BOL_ISKEEPRANGEMONSTER, false)
  end
  return 1
end

function OnCheckAutoAttackTarget(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISATTACKTARGET) == false then
    game.setrobotvar_bool(AF_BOL_ISATTACKTARGET, true)
  else
    game.setrobotvar_bool(AF_BOL_ISATTACKTARGET, false)
  end
  return 1
end

function OnPressCustomToTarget(dwID, dwCmdID, dwParam, pParam)
  game.autofightaddcustom()
  game.autofightloadtarget()
  return 1
end

function OnSelectTarget(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnSelectSurroundEnemy(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnPressDeleteTarget(dwID, dwCmdID, dwParam, pParam)
  game.autofightdeltarget()
  game.autofightloadtarget()
  return 1
end

function OnPressSurroundToTarget(dwID, dwCmdID, dwParam, pParam)
  game.autofightaddsurroundtotarget()
  game.autofightloadtarget()
  return 1
end

function OnPressRefreshSurround(dwID, dwCmdID, dwParam, pParam)
  game.autofightreloadmonster()
  return 1
end

function OnEditLowHP(dwID, dwCmdID, dwParam, pParam)
  local hp = window.gettitleint(dwID)
  if 100 < hp then
    game.setrobotvar_int(AF_INT_LOWHP, 100)
    window.settitle(dwID, 100)
  elseif hp < 0 then
    game.setrobotvar_int(AF_INT_LOWHP, 0)
    window.settitle(dwID, 0)
  else
    game.setrobotvar_int(AF_INT_LOWHP, hp)
  end
  return 1
end

function OnEditLowMP(dwID, dwCmdID, dwParam, pParam)
  local mp = window.gettitleint(dwID)
  if 100 < mp then
    game.setrobotvar_int(AF_INT_LOWMP, 100)
    window.settitle(dwID, 100)
  elseif mp < 0 then
    game.setrobotvar_int(AF_INT_LOWMP, 0)
    window.settitle(dwID, 100)
  else
    game.setrobotvar_int(AF_INT_LOWMP, mp)
  end
  return 1
end

function OnEditHighHP(dwID, dwCmdID, dwParam, pParam)
  local hp = window.gettitleint(dwID)
  if 100 < hp then
    game.setrobotvar_int(AF_INT_HIGHHP, 100)
    window.settitle(dwID, 100)
  elseif hp < 0 then
    game.setrobotvar_int(AF_INT_HIGHHP, 0)
    window.settitle(dwID, 0)
  else
    game.setrobotvar_int(AF_INT_HIGHHP, hp)
  end
  return 1
end

function OnCheckLowHP(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISRESTINLOWHP) == false then
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWHP, true)
  else
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWHP, false)
  end
  return 1
end

function OnCheckLowMP(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISRESTINLOWMP) == false then
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWMP, true)
  else
    game.setrobotvar_bool(AF_BOL_ISRESTINLOWMP, false)
  end
  return 1
end

function OnCheckHighHP(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISTRANSHPTOSP) == false then
    game.setrobotvar_bool(AF_BOL_ISTRANSHPTOSP, true)
  else
    game.setrobotvar_bool(AF_BOL_ISTRANSHPTOSP, false)
  end
  return 1
end

function OnCheckMeetBoss1(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISMEETBOSS1) == false then
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS1, true)
  else
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS1, false)
  end
  return 1
end

function OnCheckMeetBoss2(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISMEETBOSS2) == false then
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS2, true)
  else
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS2, false)
  end
  return 1
end

function OnCheckMeetBoss3(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISMEETBOSS3) == false then
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS3, true)
  else
    game.setrobotvar_bool(AF_BOL_ISMEETBOSS3, false)
  end
  return 1
end

function OnCheckAutoInvoke1(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISINVOKE1) == false then
    game.setrobotvar_bool(AF_BOL_ISINVOKE1, true)
  else
    game.setrobotvar_bool(AF_BOL_ISINVOKE1, false)
  end
  return 1
end

function OnCheckAutoInvoke2(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISINVOKE2) == false then
    game.setrobotvar_bool(AF_BOL_ISINVOKE2, true)
  else
    game.setrobotvar_bool(AF_BOL_ISINVOKE2, false)
  end
  return 1
end

function OnCheckAutoMakeCloning(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISMAKECLONING) == false then
    game.setrobotvar_bool(AF_BOL_ISMAKECLONING, true)
  else
    game.setrobotvar_bool(AF_BOL_ISMAKECLONING, false)
  end
  return 1
end

function OnRClickAutoBackItem(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearbackitem()
  return 1
end

function OnDropAutoBackItem(dwID, dwCmdID, dwParam, pParam)
  local bIsDroped, nType, nValue = game.autofightdropbackitem(pParam)
  if bIsDroped == false then
    return 0
  end
  window.setappdatafordualint(dwID, nType, nValue)
  return 1
end

function OnDropAutoInvoke(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropinvoke(pParam)
  return 1
end

function OnRClickAutoInvoke(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearinvoke()
  return 1
end

function OnDropAutoMakeCloning(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropmakecloning(pParam)
  return 1
end

function OnRClickAutoMakeCloning(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearmakecloning()
  return 1
end

function OnPressSetSearchPoint(dwID, dwCmdID, dwParam, pParam)
  game.autofightsetorgpos()
  local mapid = game.getmapid()
  game.setrobotvar_int(AF_INT_ORGMAPID, mapid)
  game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
  game.setrobotvar_bool(AF_BOL_ISSHOWAREA, true)
  CreateStageMapWnd()
  return 1
end

function OnPressViewSearchArea(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_STAGEMAP) then
    OnCloseStageMapWnd()
  else
    game.setrobotvar_bool(AF_BOL_ISSHOWAREA, true)
    CreateStageMapWnd()
  end
  return 1
end

function OnDropAutoSPAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropskill(10050, AF_INT_SPSKILL, pParam)
  return 1
end

function OnRClickAutoSPAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearskill(10050, pParam)
  game.setrobotvar_int(AF_INT_SPSKILL, 0)
  return 1
end

function OnEditNumSP(dwID, dwCmdID, dwParam, pParam)
  local num = window.gettitleint(dwID)
  if 10 < num then
    game.setrobotvar_int(AF_INT_NUMSP, 10)
    window.settitle(dwID, 10)
  elseif num < 0 then
    game.setrobotvar_int(AF_INT_NUMSP, 0)
    window.settitle(dwID, 0)
  else
    game.setrobotvar_int(AF_INT_NUMSP, num)
  end
  return 1
end

function OnEditNumGroupAttack(dwID, dwCmdID, dwParam, pParam)
  local num = window.gettitleint(dwID)
  if 20 < num then
    game.setrobotvar_int(AF_INT_NUMGROUPATTACK, 20)
    window.settitle(dwID, 20)
  elseif num < 0 then
    game.setrobotvar_int(AF_INT_NUMGROUPATTACK, 0)
    window.settitle(dwID, 0)
  else
    game.setrobotvar_int(AF_INT_NUMGROUPATTACK, num)
  end
  return 1
end

function OnCheckGroupAttack(dwID, dwCmdID, dwParam, pParam)
  if game.getrobotvar_bool(AF_BOL_ISGROUPATTACK) == false then
    game.setrobotvar_bool(AF_BOL_ISGROUPATTACK, true)
  else
    game.setrobotvar_bool(AF_BOL_ISGROUPATTACK, false)
  end
  return 1
end

function OnDropAutoGroupAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightdropskill(10053, AF_INT_GROUPATTACKSKILL, pParam)
  return 1
end

function OnRClickAutoGroupAttack(dwID, dwCmdID, dwParam, pParam)
  game.autofightclearskill(10053, pParam)
  game.setrobotvar_int(AF_INT_GROUPATTACKSKILL, 0)
  return 1
end
