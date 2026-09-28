; ModuleID = "practice1"
target triple = "arm64-apple-darwin23.5.0"
target datalayout = ""

define i32 @"main"()
{
entry:
  %"e" = alloca i1
  store i1 0, i1* %"e"
  store i1 1, i1* %"e"
  %"e.1" = load i1, i1* %"e"
  %".4" = getelementptr [5 x i8], [5 x i8]* @"true_str", i32 0, i32 0
  %".5" = getelementptr [6 x i8], [6 x i8]* @"false_str", i32 0, i32 0
  %".6" = select  i1 %"e.1", i8* %".4", i8* %".5"
  %".7" = getelementptr [29 x i8], [29 x i8]* @"fmt_bool", i32 0, i32 0
  %".8" = call i32 (i8*, ...) @"printf"(i8* %".7", i8* %".6")
  ret i32 0
}

declare i32 @"printf"(i8* %".1", ...)

@"fmt" = private constant [31 x i8] c"Program exit with result %lld\0a\00"
@"fmt_bool" = private constant [29 x i8] c"Program exit with result %s\0a\00"
@"true_str" = private constant [5 x i8] c"true\00"
@"false_str" = private constant [6 x i8] c"false\00"