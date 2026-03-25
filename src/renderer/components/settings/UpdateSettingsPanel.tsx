import { FolderOpen, RefreshCw, Rocket } from 'lucide-react';
import type { DesktopAppInfo } from '../../../shared/types';

type UpdateSettingsPanelProps = {
  appInfo: DesktopAppInfo | null;
  onOpenPlan: () => void;
  onOpenArtifacts: () => void;
  onRevealPath: (targetPath: string) => void;
};

function phaseLabel(phase: DesktopAppInfo['updaterPhase']) {
  switch (phase) {
    case 'planning':
      return 'P0 规划完成';
    case 'preparing_release':
      return 'P1 打包底座收口中';
    case 'ready_for_feed':
      return 'P2 更新源待接入';
    case 'ready_for_in_app_update':
      return 'P3 可进入应用内更新开发';
    default:
      return '阶段未定义';
  }
}

export function UpdateSettingsPanel({ appInfo, onOpenPlan, onOpenArtifacts, onRevealPath }: UpdateSettingsPanelProps) {
  return (
    <div className="bg-white border border-gray-100 rounded-3xl p-6 shadow-sm space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[16px] font-bold text-gray-900">版本与更新</h2>
          <p className="text-[12px] text-gray-500 mt-1">
            当前先按官网分发版推进。第一次从官网下载安装，后续版本通过软件内更新能力完成下载与安装。
          </p>
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[11px] font-bold text-[#335CFF]">
          {appInfo ? phaseLabel(appInfo.updaterPhase) : '正在读取桌面信息'}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前版本</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">{appInfo?.appVersion || '读取中…'}</p>
          <p className="mt-2 text-[12px] text-gray-500">
            {appInfo ? `${appInfo.platform} · ${appInfo.arch}` : '等待主进程返回版本信息'}
          </p>
        </div>
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前形态</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">{appInfo?.isPackaged ? '打包态' : '开发态'}</p>
          <p className="mt-2 text-[12px] text-gray-500">
            {appInfo ? `默认渠道：${appInfo.updateChannel}` : '尚未进入正式分发状态'}
          </p>
        </div>
        <div className="rounded-[24px] border border-gray-200 bg-gray-50 px-4 py-4">
          <p className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.16em]">当前更新能力</p>
          <p className="mt-3 text-[18px] font-bold text-gray-900">规划与入口已落</p>
          <p className="mt-2 text-[12px] text-gray-500">下一步先收口签名、公证、更新源，再接自动下载。</p>
        </div>
      </div>

      <div className="rounded-[28px] border border-blue-100 bg-blue-50/70 px-5 py-4 text-[12px] leading-6 text-[#4256C5]">
        这版先把“官网分发 + 应用内更新”的路线固定下来。真正的自动更新按钮会在签名、公证和官网更新源准备完成后再接入，避免在错误的底座上做表面功能。
      </div>

      <div className={`rounded-[28px] border px-5 py-4 text-[12px] leading-6 ${appInfo?.installStatus === 'warning' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em]">安装入口自检</p>
            <p className="mt-2 font-semibold">
              {appInfo?.installWarning || '当前只检测到单一入口，装错包风险较低。'}
            </p>
            {appInfo?.appBundlePath && (
              <div className="mt-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px] text-slate-600">
                <p className="font-bold text-slate-800">当前运行包</p>
                <p className="mt-1 break-all">{appInfo.appBundlePath}</p>
              </div>
            )}
            {appInfo?.recommendedInstallPath && (
              <div className="mt-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px] text-slate-600">
                <p className="font-bold text-slate-800">唯一建议安装入口</p>
                <p className="mt-1 break-all">{appInfo.recommendedInstallPath}</p>
                <p className="mt-2 text-[11px] text-slate-500">日常只从这个路径启动，避免继续误开历史包或临时构建包。</p>
              </div>
            )}
          </div>
          {appInfo?.appBundlePath && (
            <button
              type="button"
              className="rounded-2xl border border-current/20 bg-white/80 px-3 py-2 text-[11px] font-bold hover:bg-white"
              onClick={() => onRevealPath(appInfo.appBundlePath)}
            >
              定位当前包
            </button>
          )}
        </div>

        {appInfo && appInfo.detectedAppPaths.length > 1 && (
          <div className="mt-4 space-y-2">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em]">检测到的相关安装包</p>
            <div className="space-y-2">
              {appInfo.detectedAppPaths.map((targetPath) => {
                const isCurrent = targetPath === appInfo.appBundlePath;
                const isLegacy = appInfo.legacyAppPaths.includes(targetPath);
                return (
                  <div key={targetPath} className="flex items-center justify-between gap-3 rounded-2xl bg-white/80 px-3 py-3 text-[11px]">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-bold text-slate-800">{isCurrent ? '当前运行包' : isLegacy ? '旧入口' : '重复安装包'}</span>
                        {isLegacy && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">建议清理</span>}
                      </div>
                      <p className="mt-1 break-all text-slate-600">{targetPath}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-2xl border border-gray-200 bg-white px-3 py-2 text-[11px] font-bold text-gray-700 hover:bg-gray-50"
                      onClick={() => onRevealPath(targetPath)}
                    >
                      在 Finder 中显示
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl bg-[#5B7BFE] px-5 py-3 text-[13px] font-bold text-white shadow-sm hover:bg-[#4a6be6]"
          onClick={onOpenPlan}
        >
          <Rocket size={15} />
          查看完整计划
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-[13px] font-bold text-gray-700 shadow-sm hover:bg-gray-50"
          onClick={onOpenArtifacts}
        >
          <FolderOpen size={15} />
          打开构建产物目录
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-[13px] font-bold text-gray-400 shadow-sm cursor-not-allowed"
          disabled
        >
          <RefreshCw size={15} />
          检查更新（待接入）
        </button>
      </div>
    </div>
  );
}
