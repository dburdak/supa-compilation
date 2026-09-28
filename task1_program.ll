; ModuleID = "practice1"
target triple = "arm64-apple-darwin23.5.0"
target datalayout = ""

define i32 @"main"()
{
entry:
  %"wide" = sext i32 10 to i64
  %"a" = alloca i64
  store i64 %"wide", i64* %"a"
  %"b" = alloca i1
  store i1 1, i1* %"b"
  %"c" = alloca i1
  store i1 0, i1* %"c"
  %"a.1" = load i64, i64* %"a"
  %"wide.1" = sext i32 10 to i64
  %".5" = icmp eq i64 %"a.1", %"wide.1"
  %"d" = alloca i1
  store i1 %".5", i1* %"d"
  %"a.2" = load i64, i64* %"a"
  %"wide.2" = sext i32 10 to i64
  %".7" = icmp ne i64 %"a.2", %"wide.2"
  %"e" = alloca i1
  store i1 %".7", i1* %"e"
  %"b.1" = load i1, i1* %"b"
  %"d.1" = load i1, i1* %"d"
  %".9" = icmp eq i1 %"b.1", %"d.1"
  store i1 %".9", i1* %"e"
  %"x" = alloca i32
  store i32 15, i32* %"x"
  %"x.1" = load i32, i32* %"x"
  %"wide.3" = sext i32 %"x.1" to i64
  %"y" = alloca i64
  store i64 %"wide.3", i64* %"y"
  %"x.2" = load i32, i32* %"x"
  %".13" = add i32 %"x.2", 10
  %"wide.4" = sext i32 %".13" to i64
  %"z" = alloca i64
  store i64 %"wide.4", i64* %"z"
  %"y.1" = load i64, i64* %"y"
  %"z.1" = load i64, i64* %"z"
  %".15" = mul i64 %"y.1", %"z.1"
  %"a.3" = load i64, i64* %"a"
  %".16" = add i64 %".15", %"a.3"
  store i64 %".16", i64* %"y"
  %"y.2" = load i64, i64* %"y"
  %".18" = getelementptr [31 x i8], [31 x i8]* @"fmt", i32 0, i32 0
  %".19" = call i32 (i8*, ...) @"printf"(i8* %".18", i64 %"y.2")
  ret i32 0
}

declare i32 @"printf"(i8* %".1", ...)

@"fmt" = private constant [31 x i8] c"Program exit with result %lld\0a\00"
@"fmt_bool" = private constant [29 x i8] c"Program exit with result %s\0a\00"
@"true_str" = private constant [5 x i8] c"true\00"
@"false_str" = private constant [6 x i8] c"false\00"