ASSIST_LIST_RES_ID = 14060
ASSIST_LIST_ADD_SKILL_BTN_RES_ID = 14126
ASSIST_LIST_ADD_TARGET1_BTN_RES_ID = 14075
ASSIST_LIST_ADD_TARGET2_BTN_RES_ID = 14076
ASSIST_LIST_ADD_TARGET3_BTN_RES_ID = 14077
ASSIST_LIST_ADD_TARGET4_BTN_RES_ID = 14078
ASSIST_SKILL_BUTTON1_RES_ID = 14121
DATAID_USED_TP_ITEM = 2000
ASSIST_RES_DIFF = 12000
DATAID_RECOVER_HP_CHECK = 2001
DATAID_RECOVER_HP1_LOW_BOUND = 2003
DATAID_RECOVER_HP2_LOW_BOUND = 2009
DATAID_RECOVER_HP3_LOW_BOUND = 2015
DATAID_RECOVER_MP_CHECK = 2030
DATAID_RECOVER_MP1_LOW_BOUND = 2032
DATAID_RECOVER_MP2_LOW_BOUND = 2038
DATAID_RECOVER_SP_LOW_BOUND = 2042
DATAID_USE_ASSIST_CHECK = 2051
DATAID_USE_ASSIST_LIST = 2060
DATAID_EXERCISE_SKILL_CHECK = 2090
DATAID_EXERCISE_SUPPLY_ENABLE = 2092
DATAID_AUTO_RESURRECTION_CHECK = 2100
DATAID_AUTO_RESURRECTION_MODE = 2102
DATAID_AUTO_HELP_RESURRECTION_CHECK = 2110
DATAID_AUTO_HELP_RESURRECTION_TARGET = 2112
DATAID_AUTO_REPLY_RESURRECTION_CHECK = 2116
DATAID_AUTO_REPLY_RESURRECTION_ANSWER = 2117
DATAID_RECOVER_HP1_SKILLITEM = 2121
DATAID_RECOVER_HP2_SKILLITEM = 2122
DATAID_RECOVER_HP3_SKILLITEM = 2123
DATAID_RECOVER_MP1_SKILLITEM = 2124
DATAID_RECOVER_MP2_SKILLITEM = 2125
DATAID_USE_ASSIST_ADD_SKILLITEM = 2126
DATAID_EXERCISE_SKILL1_SKILLITEM = 2127
DATAID_EXERCISE_SKILL2_SKILLITEM = 2128
DATAID_RECOVER_SP_SKILLITEM = 2129
SKILLITEM_TYPE_DIFF = 0
SKILLITEM_VALUE_DIFF = 10
AS_BOL_CONTINUEEXERCISE = 1522

function CreateAssistWindow(WND_AUTOASSIST)
  window.trace("CreateAssistWindow")
  game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
  if game.isdef("__ROBOT2_PLUS") then
    local dwWnd = window.find(WND_AUTOASSIST, 14092)
    window.show(dwWnd, true)
  else
    local dwWnd = window.find(WND_AUTOASSIST, 14092)
    window.show(dwWnd, false)
  end
  InitialAssistWindow_CheckButton(WND_AUTOASSIST)
  InitialTextEdit(WND_AUTOASSIST)
  InitialAssistWindow_PopList(WND_AUTOASSIST)
  InitialAssistWindow_SkillItemButton(WND_AUTOASSIST)
  InitialAssistWindow_AssistList(WND_AUTOASSIST)
  InitialAssistWindow_ReplayResRadioButton(WND_AUTOASSIST)
  return 1
end

function InitialAssistWindow_CheckButton(dwMainWndHD)
  window.trace("InitialAssistWindow_CheckButton")
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_RECOVER_HP_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_RECOVER_MP_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_USE_ASSIST_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_EXERCISE_SKILL_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_AUTO_RESURRECTION_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_AUTO_HELP_RESURRECTION_CHECK, ASSIST_RES_DIFF)
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_AUTO_REPLY_RESURRECTION_CHECK, ASSIST_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_SP_LOW_BOUND, ASSIST_RES_DIFF)
  if game.isdef("__ROBOT2_PLUS") then
    LoadCheckButtonForDATAID(dwMainWndHD, DATAID_EXERCISE_SUPPLY_ENABLE, ASSIST_RES_DIFF)
  end
  return 1
end

function LoadCheckButtonForDATAID(dwMainWndHD, dataid, RES_DIFF)
  local dwSelectedWndHD = window.find(dwMainWndHD, dataid + RES_DIFF)
  local bIsCheck = game.getrobotvar_bool(dataid)
  window.setcheck(dwSelectedWndHD, bIsCheck)
  return 0
end

function InitialTextEdit(dwMainWndHD)
  window.trace("InitialAssistWindow_CheckButton")
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_HP1_LOW_BOUND, ASSIST_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_HP2_LOW_BOUND, ASSIST_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_HP3_LOW_BOUND, ASSIST_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_MP1_LOW_BOUND, ASSIST_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_RECOVER_MP2_LOW_BOUND, ASSIST_RES_DIFF)
  return 1
end

function LoadIntTextEditForDATAID(dwMainWndHD, dataid, RES_DIFF)
  local dwSelectedWndHD = window.find(dwMainWndHD, dataid + RES_DIFF)
  local nLowBoundValue = game.getrobotvar_int(dataid)
  window.settitle(dwSelectedWndHD, nLowBoundValue)
  return 0
end

function InitialAssistWindow_PopList(dwMainWndHD)
  window.trace("InitialAssistWindow_PopList")
  local dwSelectedWndHD = window.find(dwMainWndHD, DATAID_AUTO_RESURRECTION_MODE + ASSIST_RES_DIFF)
  local nStrIndex = game.getrobotvar_int(DATAID_AUTO_RESURRECTION_MODE)
  local strNewTitle = game.getstring(1955 + nStrIndex)
  window.settitle(dwSelectedWndHD, strNewTitle)
  dwSelectedWndHD = window.find(dwMainWndHD, DATAID_AUTO_HELP_RESURRECTION_TARGET + ASSIST_RES_DIFF)
  nStrIndex = game.getrobotvar_int(DATAID_AUTO_HELP_RESURRECTION_TARGET)
  if nStrIndex == 0 then
    strNewTitle = game.getstring(1952)
  else
    strNewTitle = game.getstring(1958)
  end
  window.settitle(dwSelectedWndHD, strNewTitle)
  return 1
end

function InitialAssistWindow_SkillItemButton(dwMainWndHD)
  window.trace("Initial skill/item dynamic button start")
  local dwButtonID, nType, nValue
  for i = 0, 8 do
    dwButtonID = window.find(dwMainWndHD, ASSIST_SKILL_BUTTON1_RES_ID + i)
    if i ~= 5 then
      nType = game.getrobotvar_int(ASSIST_SKILL_BUTTON1_RES_ID - ASSIST_RES_DIFF + SKILLITEM_TYPE_DIFF + i)
      nValue = game.getrobotvar_int(ASSIST_SKILL_BUTTON1_RES_ID - ASSIST_RES_DIFF + SKILLITEM_VALUE_DIFF + i)
      game.assistsetmagicitem(dwButtonID, nType, nValue)
      window.setappdatafordualint(dwButtonID, nType, nValue)
    else
      game.assistclearmagicitem(dwButtonID)
      SetupAssistListTargetCheckBox(dwMainWndHD, 0, 0)
    end
  end
  return 1
end

function InitialAssistWindow_AssistList(dwMainWndHD)
  window.trace("Initial assist skill/item list start")
  local nListNumber = game.robotvar_getnum_list(DATAID_USE_ASSIST_LIST)
  local nTypeValue, nType, nValue, nTargetByteIndex
  local dwListWndHD = window.find(dwMainWndHD, ASSIST_LIST_RES_ID)
  window.clearlist(dwListWndHD)
  for i = 0, nListNumber - 1 do
    nTypeValue = game.getrobotvar1_int2list(DATAID_USE_ASSIST_LIST, i)
    nType, nValue = game.gettypevaluefromint(nTypeValue)
    nTargetByteIndex = game.getrobotvar2_int2list(DATAID_USE_ASSIST_LIST, i)
    window.trace("list data[" .. i .. "]nType:" .. nType .. ",nValue:" .. nValue .. ",nTargetByteIndex" .. nTargetByteIndex)
    local nIndex = game.assistlistadditem(dwListWndHD, nType, nValue, nTargetByteIndex)
    if nIndex == -2 then
      return 0
    end
    if i == nListNumber - 1 then
      OnClickAssistList(dwListWndHD, 0, i, 0)
    end
  end
  return 1
end

function InitialAssistWindow_ReplayResRadioButton(dwMainWndHD)
  local dwAgreeWndHD = window.find(dwMainWndHD, DATAID_AUTO_REPLY_RESURRECTION_ANSWER + ASSIST_RES_DIFF)
  local dwRefuseWndHD = window.find(dwMainWndHD, DATAID_AUTO_REPLY_RESURRECTION_ANSWER + 1 + ASSIST_RES_DIFF)
  local bIsAgree = game.getrobotvar_int(DATAID_AUTO_REPLY_RESURRECTION_ANSWER)
  if bIsAgree ~= 1 then
    window.setcheck(dwAgreeWndHD, false)
    window.setcheck(dwRefuseWndHD, true)
  else
    window.setcheck(dwAgreeWndHD, true)
    window.setcheck(dwRefuseWndHD, false)
  end
  window.trace("InitialAssistWindow_ReplayResRadioButton bIsAgree:" .. (bIsAgree and "true" or "false"))
  return 1
end

function OnClickAssistCheckButton(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
  local bIsCheck = window.ischeck(dwID)
  if SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_RECOVER_HP_CHECK, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_RECOVER_MP_CHECK, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_USE_ASSIST_CHECK, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_EXERCISE_SUPPLY_ENABLE, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_EXERCISE_SKILL_CHECK, ASSIST_RES_DIFF) then
    if bIsCheck then
      game.insertstringtohistory(game.getstring(1966))
      if game.isdef("__ROBOT2_PLUS") then
        game.setrobotvar_bool(AS_BOL_CONTINUEEXERCISE, true)
      end
      local dwAutoFightCheckWndHD = window.find(WND_AUTOFIGHT, 960)
      window.setcheck(dwAutoFightCheckWndHD, false)
      game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, false)
      local dwAutoGatherCheckWndHD = window.find(WND_AUTOPRODUCE, DATAID_AUTO_GATHER_CHECK + PRODUCE_RES_DIFF)
      window.setcheck(dwAutoGatherCheckWndHD, false)
      game.setrobotvar_bool(DATAID_AUTO_GATHER_CHECK, false)
    else
      game.insertstringtohistory(game.getstring(1967))
    end
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_AUTO_RESURRECTION_CHECK, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_AUTO_HELP_RESURRECTION_CHECK, ASSIST_RES_DIFF) then
    return 1
  elseif SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_AUTO_REPLY_RESURRECTION_CHECK, ASSIST_RES_DIFF) then
    return 1
  end
  return 0
end

function SaveCheckButtonForDATAID(dwMainWndHD, dwID, dataid, RES_DIFF)
  if dwID == window.find(dwMainWndHD, dataid + RES_DIFF) then
    game.setrobotvar_bool(dataid, window.ischeck(dwID))
    return true
  end
  return false
end

function OnHPMPLowBoundInput(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local nLowBoundValue = tonumber(window.gettitle(dwID))
  if nLowBoundValue == nil then
    nLowBoundValue = 0
  elseif 100 < nLowBoundValue then
    nLowBoundValue = 100
  elseif nLowBoundValue < 0 then
    nLowBoundValue = 0
  end
  window.settitle(dwID, tostring(nLowBoundValue))
  if SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_HP1_LOW_BOUND) then
    return 1
  elseif SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_HP2_LOW_BOUND) then
    return 1
  elseif SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_HP3_LOW_BOUND) then
    return 1
  elseif SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_MP1_LOW_BOUND) then
    return 1
  elseif SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_MP2_LOW_BOUND) then
    return 1
  elseif SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, DATAID_RECOVER_SP_LOW_BOUND) then
    return 1
  end
  return 0
end

function SaveHPMPLowBoundForDATAID(dwMainWndHD, dwID, nLowBoundValue, dataid)
  if dwID == window.find(dwMainWndHD, dataid + ASSIST_RES_DIFF) then
    game.setrobotvar_int(dataid, nLowBoundValue)
    return true
  end
  return false
end

function OnDropAssistMagicItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnDropAssistMagicItem")
  local dwMainWndHD = window.parent(dwID)
  local bIsDroped, nType, nValue = game.assistdropmagicitem(dwID, pParam)
  if bIsDroped == false then
    return 0
  end
  if SaveALLSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue) then
    return 1
  end
  return 0
end

function SaveALLSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue)
  if SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_HP1_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_HP2_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_HP3_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_MP1_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_MP2_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_RECOVER_SP_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_USE_ASSIST_ADD_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_EXERCISE_SKILL1_SKILLITEM) then
    return true
  elseif SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, DATAID_EXERCISE_SKILL2_SKILLITEM) then
    return true
  end
  return false
end

function SaveSkillItemButtonForDATAID(dwMainWndHD, dwID, nType, nValue, dataid)
  if dwID == window.find(dwMainWndHD, dataid + ASSIST_RES_DIFF) then
    window.setappdatafordualint(dwID, nType, nValue)
    if dataid == DATAID_USE_ASSIST_ADD_SKILLITEM then
      SetupAssistListTargetCheckBox(dwMainWndHD, nType, nValue)
      return true
    else
      game.setrobotvar_int(dataid + SKILLITEM_TYPE_DIFF, nType)
      game.setrobotvar_int(dataid + SKILLITEM_VALUE_DIFF, nValue)
      return true
    end
  end
  return false
end

function SetupAssistListTargetCheckBox(dwMainWndHD, nType, nValue)
  local dwTarget1BtnWndHD = window.find(dwMainWndHD, ASSIST_LIST_ADD_TARGET1_BTN_RES_ID)
  local dwTarget2BtnWndHD = window.find(dwMainWndHD, ASSIST_LIST_ADD_TARGET2_BTN_RES_ID)
  local dwTarget3BtnWndHD = window.find(dwMainWndHD, ASSIST_LIST_ADD_TARGET3_BTN_RES_ID)
  local dwTarget4BtnWndHD = window.find(dwMainWndHD, ASSIST_LIST_ADD_TARGET4_BTN_RES_ID)
  local bSelf, bPartner, bSelfPet, bPartnerPet = window.getassistcheckboxenableinfo(nType, nValue)
  window.setcheck(dwTarget1BtnWndHD, false)
  window.setcheck(dwTarget2BtnWndHD, false)
  window.setcheck(dwTarget3BtnWndHD, false)
  window.setcheck(dwTarget4BtnWndHD, false)
  window.enable(dwTarget1BtnWndHD, bSelf)
  window.enable(dwTarget2BtnWndHD, bPartner)
  window.enable(dwTarget3BtnWndHD, bSelfPet)
  window.enable(dwTarget4BtnWndHD, bPartnerPet)
  return 0
end

function OnClearAssistMagicItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnClearAssistMagicItem")
  game.assistclearmagicitem(dwID)
  local dwMainWndHD = window.parent(dwID)
  if SaveALLSkillItemButtonForDATAID(dwMainWndHD, dwID, 0, 0) then
    return 1
  else
    return 0
  end
end

function OnTooltipAssistMagicItem(dwID, dwCmdID, dwParam, pParam)
  local nType, nValue = window.getappdatafordualint(dwID)
  if nType == 0 then
    return 0
  end
  game.ontooltipassistmagicitem(dwID, nType, nValue)
  return 1
end

function SkillUsedTargetPopListDown(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local list_hd = window.create(14076, Wnd, 0, 0)
  if list_hd ~= nil then
    window.insertitemstr(list_hd, game.getstring(1951), 0)
    window.insertitemstr(list_hd, game.getstring(1952), 0)
    window.insertitemstr(list_hd, game.getstring(1953), 0)
    window.insertitemstr(list_hd, game.getstring(1954), 0)
  end
  return 1
end

function ResurrectionPopListDown(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local list_hd = window.create(14104, Wnd, 0, 0)
  if list_hd ~= nil then
    window.insertitemstr(list_hd, game.getstring(1955), 0)
    window.insertitemstr(list_hd, game.getstring(1956), 0)
    window.insertitemstr(list_hd, game.getstring(1957), 0)
  end
  return 1
end

function ResurrectionSelected(dwID, dwCmdID, dwParam, pParam)
  local dwParentWndID = window.parent(dwID)
  local dwSelectedWndHD = window.find(dwParentWndID, 14102)
  local strNewTitle = game.getstring(1955 + dwParam)
  window.settitle(dwSelectedWndHD, strNewTitle)
  game.setrobotvar_int(DATAID_AUTO_RESURRECTION_MODE, dwParam)
  window.destroy(dwID)
  return 1
end

function HelpResurrectionPopListDown(dwID, dwCmdID, dwParam, pParam)
  local Wnd = window.parent(dwID)
  local list_hd = window.create(14114, Wnd, 0, 0)
  if list_hd ~= nil then
    window.insertitemstr(list_hd, game.getstring(1952), 0)
    window.insertitemstr(list_hd, game.getstring(1958), 0)
  end
  return 1
end

function HelpResurrectionSelected(dwID, dwCmdID, dwParam, pParam)
  local dwParentWndHD = window.parent(dwID)
  local dwSelectedWndHD = window.find(dwParentWndHD, 14112)
  local strNewTitle
  if dwParam == 0 then
    strNewTitle = game.getstring(1952)
  else
    strNewTitle = game.getstring(1958)
  end
  window.settitle(dwSelectedWndHD, strNewTitle)
  game.setrobotvar_int(DATAID_AUTO_HELP_RESURRECTION_TARGET, dwParam)
  window.destroy(dwID)
  return 1
end

function OnAddAutoUseAssistSkillItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnAddAutoUseAssistSkillItem")
  local dwParentWndHD = window.parent(dwID)
  local dwListWndHD = window.find(dwParentWndHD, ASSIST_LIST_RES_ID)
  local dwSkillBtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_SKILL_BTN_RES_ID)
  local dwTarget1BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET1_BTN_RES_ID)
  local dwTarget2BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET2_BTN_RES_ID)
  local dwTarget3BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET3_BTN_RES_ID)
  local dwTarget4BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET4_BTN_RES_ID)
  local nType, nValue = window.getappdatafordualint(dwSkillBtnWndHD)
  if nType == 0 then
    window.trace("OnAddAutoUseAssistSkillItem:Skill//Item btn is empty.")
    return 0
  end
  local nTargetByteIndex = window.getbyteindexfromtargetbtn(dwListWndHD, dwTarget1BtnWndHD, dwTarget2BtnWndHD, dwTarget3BtnWndHD, dwTarget4BtnWndHD)
  if nTargetByteIndex == 0 then
    return 0
  end
  local nAddIndex = game.assistlistadditem(dwListWndHD, nType, nValue, nTargetByteIndex)
  if nAddIndex == -2 then
    window.trace("OnAddAutoUseAssistSkillItem:add to assist list fail.")
    return 0
  end
  local nTypeValue = game.getintfromtypevalue(nType, nValue)
  if nAddIndex == -1 then
    game.robotvar_add_int2list(DATAID_USE_ASSIST_LIST, nTypeValue, nTargetByteIndex)
  elseif 0 <= nAddIndex then
    game.setrobotvar_int2list(DATAID_USE_ASSIST_LIST, nAddIndex, nTypeValue, nTargetByteIndex)
  end
  return 1
end

function OnRemoveAutoUseAssistSkillItem(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnRemoveAutoUseAssistSkillItem")
  local dwParentWndHD = window.parent(dwID)
  local dwListWndHD = window.find(dwParentWndHD, ASSIST_LIST_RES_ID)
  local nCheckIndex = window.getlistcheckitem(dwListWndHD)
  game.removerobotvar_int2list(DATAID_USE_ASSIST_LIST, nCheckIndex)
  game.assistlistremoveitem(dwListWndHD)
  return 1
end

function OnClickAssistList(dwID, dwCmdID, dwParam, pParam)
  window.trace("OnClickAssistList")
  local dwParentWndHD = window.parent(dwID)
  local nType, nValue, bTarget1, bTarget2, bTarget3, bTarget4 = game.assistlistgetitemdata(dwID, dwParam)
  if nType == 0 then
    window.trace("OnClickAssistList:game.assistlistgetitemdata fail")
    return 0
  end
  local dwSkillBtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_SKILL_BTN_RES_ID)
  local dwTarget1BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET1_BTN_RES_ID)
  local dwTarget2BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET2_BTN_RES_ID)
  local dwTarget3BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET3_BTN_RES_ID)
  local dwTarget4BtnWndHD = window.find(dwParentWndHD, ASSIST_LIST_ADD_TARGET4_BTN_RES_ID)
  game.assistsetmagicitem(dwSkillBtnWndHD, nType, nValue)
  SaveSkillItemButtonForDATAID(dwParentWndHD, dwSkillBtnWndHD, nType, nValue, DATAID_USE_ASSIST_ADD_SKILLITEM)
  window.setcheck(dwTarget1BtnWndHD, bTarget1)
  window.setcheck(dwTarget2BtnWndHD, bTarget2)
  window.setcheck(dwTarget3BtnWndHD, bTarget3)
  window.setcheck(dwTarget4BtnWndHD, bTarget4)
  return 1
end

function OnRadioAutoReplyResAgree(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(DATAID_AUTO_REPLY_RESURRECTION_ANSWER, 1)
  window.trace("OnRadioAutoReplyResAgree")
  return 0
end

function OnRadioAutoReplyResRefuse(dwID, dwCmdID, dwParam, pParam)
  game.setrobotvar_int(DATAID_AUTO_REPLY_RESURRECTION_ANSWER, 0)
  window.trace("OnRadioAutoReplyResRefuse")
  return 0
end

HISTORY_LOG_LIST_RES_ID = 14301
DATAID_HISTORY_LOG_LIST = 9000

function CreateHistoryLogWindow(WND_AUTOHISTORYLOG)
  window.trace("CreateHistoryLogWindow")
  InitialHistoryWindow_List(WND_AUTOHISTORYLOG)
  return 1
end

function InitialHistoryWindow_List(dwMainWndHD)
  window.trace("Initial History Log list start")
  local dwListWndHD = window.find(dwMainWndHD, HISTORY_LOG_LIST_RES_ID)
  LoadStringListForDataID(dwMainWndHD, HISTORY_LOG_LIST_RES_ID, DATAID_HISTORY_LOG_LIST)
  window.scrolllisttolast(dwListWndHD)
  return 1
end

function OnClickClearAutoRobotHistoryWnd(dwID, dwCmdID, dwParam, pParam)
  local dwParentWndHD = window.parent(dwID)
  local dwListWndHD = window.find(dwParentWndHD, HISTORY_LOG_LIST_RES_ID)
  window.clearlist(dwListWndHD)
  game.robotvar_clear_list(DATAID_HISTORY_LOG_LIST)
  return 0
end

function LoadStringListForDataID(dwMainWndHD, nListResID, dataid)
  local dwListWndHD = window.find(dwMainWndHD, nListResID)
  local nListNumber = game.robotvar_getnum_list(dataid)
  local nStringLine
  window.clearlist(dwListWndHD)
  for i = 0, nListNumber - 1 do
    nStringLine = game.getrobotvar_stringlist(dataid, i)
    if nStringLine ~= "" or string.sub(nStringLine, 1, 1) ~= " " then
      window.insertitemstr(dwListWndHD, nStringLine, 0)
    end
  end
  return 1
end

AUTO_GATHER_DESIGNATED_RESLIST_RES_ID = 14323
AUTO_GATHER_SURROUNDLIST_RES_ID = 14324
AUTO_GATHER_CUSTOM_TEXT_RES_ID = 14330
PRODUCE_RES_DIFF = 12000
DATAID_AUTO_GATHER_CHECK = 2311
DATAID_AUTO_GATHER_ORGMAPID = 2312
DATAID_AUTO_GATHER_RANGE = 2313
DATAID_AUTO_GATHER_ORGPOSX = 2314
DATAID_AUTO_GATHER_ORGPOSY = 2315
DATAID_DESIGNATED_GATHER_CHECK = 2320
DATAID_AUTO_GATHER_ISSHOWAREA = 2321
DATAID_AUTO_PRODUCE_DEFAULT = 2322
DATAID_DESIGNATED_RES_LIST = 2323
G_AUTOGATHER_ISINITIAL = false
G_AUTOGATHER_MAXRANGE = MAX_AUTOFIGHTRANGE

function CreateAutoProduceWindow(WND_AUTOPRODUCE)
  window.trace("CreateAutoProduceWindow")
  AutoProduceSetDefaultValue()
  InitialAutoGather(WND_AUTOPRODUCE)
  InitialDesignatedGather(WND_AUTOPRODUCE)
  return 1
end

function AutoProduceSetDefaultValue()
  if game.getrobotvar_bool(DATAID_AUTO_PRODUCE_DEFAULT) == false then
    game.setrobotvar_bool(DATAID_AUTO_GATHER_CHECK, false)
    game.setrobotvar_int(DATAID_AUTO_GATHER_RANGE, 20)
    game.setrobotvar_bool(DATAID_AUTO_PRODUCE_DEFAULT, true)
  end
  return 1
end

function InitialAutoGather(dwMainWndHD)
  window.trace("Initial Auto Gather start")
  if game.isdef("__ANGEL_WALK") then
    G_AUTOGATHER_ISINITIAL = true
  end
  if G_AUTOGATHER_ISINITIAL == false then
    game.setrobotvar_bool(DATAID_AUTO_GATHER_ISSHOWAREA, false)
    game.setrobotvar_int(DATAID_AUTO_GATHER_ORGMAPID, -1)
    game.setrobotvar_int(DATAID_AUTO_GATHER_ORGPOSX, -1)
    game.setrobotvar_int(DATAID_AUTO_GATHER_ORGPOSY, -1)
    G_AUTOGATHER_ISINITIAL = true
  end
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_AUTO_GATHER_CHECK, PRODUCE_RES_DIFF)
  LoadIntTextEditForDATAID(dwMainWndHD, DATAID_AUTO_GATHER_RANGE, PRODUCE_RES_DIFF)
  return 1
end

function InitialDesignatedGather(dwMainWndHD)
  window.trace("Initial Designated Gather start")
  LoadCheckButtonForDATAID(dwMainWndHD, DATAID_DESIGNATED_GATHER_CHECK, PRODUCE_RES_DIFF)
  LoadStringListForDataID(dwMainWndHD, DATAID_DESIGNATED_RES_LIST + PRODUCE_RES_DIFF, DATAID_DESIGNATED_RES_LIST)
  return 1
end

function OnClickAutoGatherCheckBtn(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_AUTO_GATHER_CHECK, PRODUCE_RES_DIFF)
  if window.ischeck(dwID) then
    if game.isdef("__ANGEL_WALK") then
    else
      game.autoproducesetgatherorgpos()
    end
    local mapid = game.getmapid()
    if game.isdef("__ANGEL_WALK") then
    else
      game.setrobotvar_int(DATAID_AUTO_GATHER_ORGMAPID, mapid)
    end
    game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
    local dwAutoFightCheckWndHD = window.find(WND_AUTOFIGHT, 960)
    window.setcheck(dwAutoFightCheckWndHD, false)
    game.setrobotvar_bool(AF_BOL_ISAUTOFIGHT, false)
    local dwAutoExerciseCheckWndHD = window.find(WND_AUTOASSIST, DATAID_EXERCISE_SKILL_CHECK + ASSIST_RES_DIFF)
    window.setcheck(dwAutoExerciseCheckWndHD, false)
    game.setrobotvar_bool(DATAID_EXERCISE_SKILL_CHECK, false)
  end
  return 1
end

function OnEditAutoGatherWnd(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local nRange = tonumber(window.gettitle(dwID))
  if nRange == nil then
    nRange = 0
  elseif nRange > G_AUTOGATHER_MAXRANGE then
    nRange = G_AUTOGATHER_MAXRANGE
  elseif nRange < 0 then
    nRange = 0
  end
  window.settitle(dwID, tostring(nRange))
  game.setrobotvar_int(DATAID_AUTO_GATHER_RANGE, nRange)
  return 0
end

function OnClickAutoGatherSetSearchPoint(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  game.autoproducesetgatherorgpos()
  local mapid = game.getmapid()
  game.setrobotvar_int(DATAID_AUTO_GATHER_ORGMAPID, mapid)
  game.setrobotvar_bool(DATAID_USED_TP_ITEM, false)
  game.setrobotvar_bool(DATAID_AUTO_GATHER_ISSHOWAREA, true)
  CreateStageMapWnd()
  return 1
end

function OnClickAutoGatherViewSearchArea(dwID, dwCmdID, dwParam, pParam)
  if window.isexist(WND_STAGEMAP) then
    OnCloseStageMapWnd()
  else
    game.setrobotvar_bool(DATAID_AUTO_GATHER_ISSHOWAREA, true)
    CreateStageMapWnd()
  end
  return 1
end

function OnClickDesignatedGatherCheckBtn(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  SaveCheckButtonForDATAID(dwMainWndHD, dwID, DATAID_DESIGNATED_GATHER_CHECK, PRODUCE_RES_DIFF)
  return 1
end

function OnSelectDesignatedGatherList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  return 1
end

function OnSelectSurroundResourceList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  return 1
end

function OnClickAddToDesignatedGatherList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwDesignatedResourceListHD = window.find(dwMainWndHD, AUTO_GATHER_DESIGNATED_RESLIST_RES_ID)
  local dwSurroundResourceListHD = window.find(dwMainWndHD, AUTO_GATHER_SURROUNDLIST_RES_ID)
  game.autogatheraddsurroundtodesignatedlist(dwDesignatedResourceListHD, dwSurroundResourceListHD, DATAID_DESIGNATED_RES_LIST)
  return 1
end

function OnClickDeleteItemOfDesignatedGatherList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwDesignatedResourceListHD = window.find(dwMainWndHD, AUTO_GATHER_DESIGNATED_RESLIST_RES_ID)
  game.autogatherdeletemutipleitemoflist(dwDesignatedResourceListHD, DATAID_DESIGNATED_RES_LIST)
  return 1
end

function OnEditCustomDesignatedGatherTarget(dwID, dwCmdID, dwParam, pParam)
  return 1
end

function OnClickAddCustomToDesignatedGatherList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwDesignatedResourceListHD = window.find(dwMainWndHD, AUTO_GATHER_DESIGNATED_RESLIST_RES_ID)
  local dwCustomTextEditHD = window.find(dwMainWndHD, AUTO_GATHER_CUSTOM_TEXT_RES_ID)
  if window.gettitle(dwCustomTextEditHD) == "" then
    return 1
  end
  game.autogatheraddcustomtolist(dwDesignatedResourceListHD, window.gettitle(dwCustomTextEditHD), DATAID_DESIGNATED_RES_LIST)
  return 1
end

function OnClickRefreshSurroundResourceList(dwID, dwCmdID, dwParam, pParam)
  local dwMainWndHD = window.parent(dwID)
  local dwSurroundResourceListHD = window.find(dwMainWndHD, AUTO_GATHER_SURROUNDLIST_RES_ID)
  game.autogatherreloadresource(dwSurroundResourceListHD)
  return 1
end

local ANIMATE_LOOP = 0
local MOVE_DIRECTION_LEFT = true
local MOVE_DIRECTION_TOP = true
local FIRE_LOOP = -1

function OnJTest_U_Change(dwID, dwCmdID, dwParam, pParam)
  MOVE_DIRECTION_TOP = true
  return 1
end

function OnJTest_D_Change(dwID, dwCmdID, dwParam, pParam)
  MOVE_DIRECTION_TOP = false
  return 1
end

function OnJTest_UpdatePicture(dwID, dwCmdID, dwParam, pParam)
  if 0 <= ANIMATE_LOOP and ANIMATE_LOOP < 20 then
    window.seticon(dwID, 20120 + ANIMATE_LOOP / 5)
    ANIMATE_LOOP = ANIMATE_LOOP + 1
  elseif 20 <= ANIMATE_LOOP and ANIMATE_LOOP < 40 then
    window.seticon(dwID, 20127 - ANIMATE_LOOP / 5)
    ANIMATE_LOOP = ANIMATE_LOOP + 1
  else
    ANIMATE_LOOP = 0
    window.seticon(dwID, 20120)
  end
  local PARENT_ID = window.parent(dwID)
  local PICTURE_RIGHT = window.left(dwID) + window.width(dwID) - 22
  local PICTURE_LEFT = window.left(dwID) - 48
  local PARENT_RIGHT = window.left(PARENT_ID) + window.width(PARENT_ID)
  local PARENT_LEFT = window.left(PARENT_ID)
  if MOVE_DIRECTION_LEFT == true and PICTURE_LEFT > PARENT_LEFT then
    window.moveoffset(dwID, -1, 0)
  elseif MOVE_DIRECTION_LEFT == false and PICTURE_RIGHT < PARENT_RIGHT then
    window.moveoffset(dwID, 1, 0)
  end
  if PICTURE_LEFT <= PARENT_LEFT then
    MOVE_DIRECTION_LEFT = false
  elseif PICTURE_RIGHT >= PARENT_RIGHT then
    MOVE_DIRECTION_LEFT = true
  end
  local PICTURE_TOP = window.top(dwID) - 48
  local PICTURE_BOTTOM = window.top(dwID) + window.height(dwID) + 10
  local PARENT_TOP = window.top(PARENT_ID)
  local PARENT_BOTTOM = window.top(PARENT_ID) + window.height(PARENT_ID)
  if MOVE_DIRECTION_TOP == true and PICTURE_TOP > PARENT_TOP then
    window.moveoffset(dwID, 0, -1)
  elseif MOVE_DIRECTION_TOP == false and PICTURE_BOTTOM < PARENT_BOTTOM then
    window.moveoffset(dwID, 0, 1)
  end
  if PICTURE_TOP <= PARENT_TOP then
    MOVE_DIRECTION_TOP = false
  elseif PICTURE_BOTTOM >= PARENT_BOTTOM then
    MOVE_DIRECTION_TOP = true
  end
  return 1
end

function OnJTest_OnFire(dwID, dwCmdID, dwParam, pParam)
  FIRE_LOOP = 0
  local FIRE_ID = window.find(window.parent(dwID), 20130)
  local PARENT_LEFT = window.left(window.parent(FIRE_ID))
  local PARENT_TOP = window.top(window.parent(FIRE_ID))
  window.seticon(FIRE_ID, 20129)
  window.move(FIRE_ID, PARENT_LEFT + 200, PARENT_TOP + 350)
  return 1
end

function OnJTest_UpdateFire(dwID, dwCmdID, dwParam, pParam)
  if 0 <= FIRE_LOOP and FIRE_LOOP < 60 then
    window.moveoffset(dwID, 0, -3)
    FIRE_LOOP = FIRE_LOOP + 1
  elseif 60 <= FIRE_LOOP and FIRE_LOOP < 92 then
    window.seticon(dwID, 20130 + (FIRE_LOOP - 60) / 2)
    FIRE_LOOP = FIRE_LOOP + 1
  elseif 92 <= FIRE_LOOP and FIRE_LOOP < 110 then
    window.seticon(dwID, 20145)
    if FIRE_LOOP % 2 == 1 then
      window.moveoffset(dwID, 0, 1)
      window.modifyiconattrib(ICON_ATTRIB_MIXER, 0)
    end
    FIRE_LOOP = FIRE_LOOP + 1
  elseif 110 <= FIRE_LOOP then
    window.seticon(dwID, 20146)
    FIRE_LOOP = -1
  end
  return 1
end
