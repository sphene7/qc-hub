<template>
  <section class="code-table-view card">
    <div class="view-head">
      <div>
        <h2>类别管理</h2>
        <p v-if="sheetSpec?.note" class="hint">{{ sheetSpec.note }}</p>
      </div>
      <button type="button" class="ghost-btn" :disabled="loading" @click="loadData">刷新</button>
    </div>

    <div v-if="loading" class="loading-hint">加载中…</div>
    <div v-else-if="error" class="error-hint">{{ error }}</div>

    <template v-else-if="isOqcLayout">
      <p v-if="syncHint" class="sync-hint oqc-sync-top">{{ syncHint }}</p>

      <div class="rule-tabs oqc-page-tabs">
        <button type="button" :class="{ on: oqcPage === 1 }" @click="oqcPage = 1">第一页 · 不良代码</button>
        <button type="button" :class="{ on: oqcPage === 2 }" @click="oqcPage = 2">第二页 · 机种 · 课室</button>
        <button type="button" :class="{ on: oqcPage === 3 }" @click="oqcPage = 3">第三页 · 机种 · 负责人</button>
        <button type="button" :class="{ on: oqcPage === 4 }" @click="oqcPage = 4">第四页 · 课室负责人 · 课室</button>
      </div>

      <div class="oqc-overview">
        <section v-show="oqcPage === 1" class="oqc-section">
          <header class="oqc-section-head">
            <div>
              <h3>不良代码 · 大类</h3>
              <p class="section-desc">
                共 <strong>{{ oqcDefectCategoryGroups.length }}</strong> 个大类、
                <strong>{{ totalOqcDefects }}</strong> 项代码
                <span class="overview-hint">· 主表「不良代码」自动带出「现象」</span>
              </p>
            </div>
            <button v-if="canEdit" type="button" class="primary-btn" @click="openOqcDefectMajorCreate">添加大类</button>
          </header>
          <div v-if="oqcDefectCategoryGroups.length" class="category-grid">
            <article
              v-for="group in oqcDefectCategoryGroups"
              :key="group.category"
              class="category-card"
              :class="group.className"
            >
              <header class="category-card-head">
                <h3>
                  <i class="cat-dot" :class="group.className" />
                  {{ group.category }}
                </h3>
                <span class="cat-count">{{ group.count }}</span>
                <div v-if="canEdit" class="card-head-actions">
                  <button
                    type="button"
                    class="card-add-btn"
                    title="在此大类下添加"
                    @click="openOqcDefectCreateForCategory(group.category)"
                  >+ 代码</button>
                  <button type="button" class="icon-btn" title="编辑大类" @click="openOqcDefectMajorEdit(group.category)">✏️</button>
                  <button type="button" class="icon-btn" title="删除大类" @click="confirmOqcDefectMajorDelete(group)">🗑️</button>
                </div>
              </header>
              <ul class="classification-list compact">
                <li
                  v-for="row in group.items"
                  :key="row.code"
                  class="classification-item"
                  :class="group.className"
                >
                  <span class="cls-index defect-code">{{ row.code }}</span>
                  <span class="cls-name">{{ row.desc }}</span>
                  <div v-if="canEdit" class="cls-actions">
                    <button type="button" class="icon-btn" title="编辑" @click="openOqcDefectEdit(row)">✏️</button>
                    <button type="button" class="icon-btn" title="删除" @click="confirmOqcDefectDelete(row)">🗑️</button>
                  </div>
                </li>
              </ul>
              <p v-if="!group.items.length" class="category-empty-hint">暂无代码，点击「+ 代码」添加小类</p>
            </article>
          </div>
          <p v-else class="empty-hint">暂无不良代码</p>
        </section>

        <section v-show="oqcPage === 1" class="oqc-section oqc-section--meta">
          <header class="oqc-section-head">
            <div>
              <h3>检验判定与说明</h3>
              <p class="section-desc">主表检验状态颜色含义</p>
            </div>
          </header>
          <div class="oqc-meta-cards">
            <div class="instructions instructions-card">
              <div class="instructions-title">大类描述说明</div>
          <ol>
            <li>一般部品位置：比如外部镜片部分（光圈、ICR电磁铁、G1等），性能部品按工位区分（实像、投影、作动、波形等）。</li>
            <li>结合部分：比如螺丝部分结合安防组3与后盖，描述为「镜头」。</li>
            <li>整镜头出现错混料：描述为「包装」。</li>
            <li>其他新品描述性问题，后续再检讨。</li>
          </ol>
        </div>
            <div class="status-card-grid">
              <article v-for="item in statusLegend" :key="item.label" class="status-mini-card">
                  <span class="status-code">
                    <i :class="['legend-swatch', item.className]" />
                    {{ item.label }}
                  </span>
                <span class="status-desc">{{ item.desc }}</span>
              </article>
          </div>
        </div>
        </section>

        <section v-show="oqcPage === 2" class="oqc-section">
          <header class="oqc-section-head">
            <div>
              <h3>机种 · 课室（送检单位）</h3>
              <p class="section-desc">
                共 <strong>{{ oqcModelSectionGroups.length }}</strong> 个课室（大类）、
                <strong>{{ oqcModelSectionsDisplay.length }}</strong> 项机种
                <span class="overview-hint">· 与第一页「大类」同样按课室分组</span>
              </p>
      </div>
            <button v-if="canEdit" type="button" class="primary-btn" @click="openOqcSectionMajorCreate">添加课室</button>
          </header>
          <div v-if="oqcModelSectionGroups.length" class="category-grid">
            <article
              v-for="group in oqcModelSectionGroups"
              :key="'msg-' + group.category"
              class="category-card cat-oqc-section"
            >
              <header class="category-card-head">
                <h3>
                  <i class="cat-dot cat-oqc-section" />
                  {{ group.category }}
                </h3>
                <span class="cat-count">{{ group.count }}</span>
                <div v-if="canEdit" class="card-head-actions">
                  <button
                    type="button"
                    class="card-add-btn"
                    title="在此课室下添加机种"
                    @click="openOqcModelSectionCreateForCategory(group.category)"
                  >+ 机种</button>
                  <button type="button" class="icon-btn" title="编辑课室" @click="openOqcClassroomMajorEdit(group.category)">✏️</button>
                  <button type="button" class="icon-btn" title="删除课室" @click="confirmOqcClassroomMajorDelete(group)">🗑️</button>
                </div>
              </header>
              <ul class="classification-list compact">
                <li
                  v-for="row in group.items"
                  :key="'ms-' + row.model"
                  class="classification-item cat-oqc-section"
                >
                  <span class="cls-index defect-code">{{ row.model }}</span>
                  <span class="cls-name">机种</span>
                  <div v-if="canEdit" class="cls-actions">
                    <button type="button" class="icon-btn" title="编辑" @click="openOqcModelSectionEdit(row)">✏️</button>
                    <button type="button" class="icon-btn" title="删除" @click="confirmOqcModelSectionDelete(row)">🗑️</button>
                  </div>
                </li>
              </ul>
              <p v-if="!group.items.length" class="category-empty-hint">暂无机种，点击「+ 机种」添加小类</p>
            </article>
          </div>
          <p v-else class="empty-hint">暂无机种与课室映射</p>
        </section>

        <section v-show="oqcPage === 3" class="oqc-section oqc-section--owner-table">
          <header class="oqc-section-head">
            <div>
              <h3>机种 · 负责人</h3>
              <p class="section-desc">
                共 <strong>{{ oqcModelOwnersDisplay.length }}</strong> 条映射
                <span v-if="oqcModelOwnerTableRows.length !== oqcModelOwnersDisplay.length">
                  · 当前筛选 <strong>{{ oqcModelOwnerTableRows.length }}</strong> 条
                </span>
                <span class="overview-hint">· 与 Excel 代码表第三页相同的两列对照，支持筛选</span>
              </p>
            </div>
            <div v-if="canEdit" class="oqc-section-head-actions">
              <button type="button" class="ghost-btn" @click="openOqcOwnerBulkRename">一键更换负责人</button>
              <button type="button" class="primary-btn" @click="openOqcModelOwnerCreate">添加</button>
            </div>
          </header>
          <div v-if="oqcModelOwnersDisplay.length" class="oqc-owner-table-wrap">
            <table class="oqc-owner-table">
            <thead>
                <tr class="oqc-owner-table-head">
                  <th>机种</th>
                  <th>负责人</th>
                  <th v-if="canEdit" class="col-actions">操作</th>
                </tr>
                <tr class="oqc-owner-table-filter">
                  <th>
                    <select v-model="oqcModelOwnerFilterModel" class="table-filter-select">
                      <option value="">全部机种</option>
                      <option v-for="m in oqcModelOwnerFilterModelOptions" :key="'fm-' + m" :value="m">
                        {{ m }}
                      </option>
                    </select>
                  </th>
                  <th>
                    <select v-model="oqcModelOwnerFilterOwner" class="table-filter-select">
                      <option value="">全部负责人</option>
                      <option v-for="o in oqcModelOwnerFilterOwnerOptions" :key="'fo-' + o" :value="o">
                        {{ o }}
                      </option>
                    </select>
                  </th>
                  <th v-if="canEdit">
                    <button
                      v-if="oqcModelOwnerFilterModel || oqcModelOwnerFilterOwner"
                      type="button"
                      class="ghost-btn table-filter-clear"
                      @click="clearOqcModelOwnerFilters"
                    >清除筛选</button>
                  </th>
                </tr>
            </thead>
            <tbody>
                <tr
                  v-for="row in oqcModelOwnerTableRows"
                  :key="'mo-row-' + row.model"
                  class="oqc-owner-table-row"
                >
                  <td class="col-model">{{ row.model }}</td>
                  <td class="col-owner">{{ row.owner }}</td>
                  <td v-if="canEdit" class="col-actions">
                    <button type="button" class="icon-btn" title="编辑" @click="openOqcModelOwnerEdit(row)">✏️</button>
                    <button type="button" class="icon-btn" title="删除" @click="confirmOqcModelOwnerDelete(row)">🗑️</button>
                  </td>
                </tr>
                <tr v-if="!oqcModelOwnerTableRows.length">
                  <td :colspan="canEdit ? 3 : 2" class="empty-filter-hint">无匹配记录，请调整筛选条件</td>
              </tr>
            </tbody>
          </table>
        </div>
          <p v-else class="empty-hint">暂无机种与负责人映射</p>
        </section>

        <section v-show="oqcPage === 4" class="oqc-section">
          <header class="oqc-section-head">
            <div>
              <h3>课室负责人 · 课室</h3>
              <p class="section-desc">
                共 <strong>{{ oqcSectionHeadGroups.length }}</strong> 位课室负责人（大类）、
                <strong>{{ oqcSectionHeadsDisplay.length }}</strong> 个课室
                <span class="overview-hint">· 按课室负责人分组，课室为小类</span>
              </p>
            </div>
            <button v-if="canEdit" type="button" class="primary-btn" @click="openOqcSectionHeadMajorCreate">添加课室负责人</button>
          </header>
          <div v-if="oqcSectionHeadGroups.length" class="category-grid">
            <article
              v-for="group in oqcSectionHeadGroups"
              :key="'shg-' + group.category"
              class="category-card cat-oqc-section"
            >
              <header class="category-card-head">
                <h3>
                  <i class="cat-dot cat-oqc-section" />
                  {{ group.category }}
                </h3>
                <span class="cat-count">{{ group.count }}</span>
                <div v-if="canEdit" class="card-head-actions">
                  <button
                    type="button"
                    class="card-add-btn"
                    title="在此负责人下添加课室"
                    @click="openOqcSectionHeadCreateForCategory(group.category)"
                  >+ 课室</button>
                  <button type="button" class="icon-btn" title="编辑课室负责人" @click="openOqcSectionHeadMajorEdit(group.category)">✏️</button>
                  <button type="button" class="icon-btn" title="删除课室负责人" @click="confirmOqcSectionHeadMajorDelete(group)">🗑️</button>
                </div>
              </header>
              <ul class="classification-list compact">
                <li
                  v-for="row in group.items"
                  :key="'sh-' + row.section"
                  class="classification-item cat-oqc-section"
                >
                  <span class="cls-index defect-code">{{ row.section }}</span>
                  <span class="cls-name">课室</span>
                  <div v-if="canEdit" class="cls-actions">
                    <button type="button" class="icon-btn" title="编辑" @click="openOqcSectionHeadEdit(row)">✏️</button>
                    <button type="button" class="icon-btn" title="删除" @click="confirmOqcSectionHeadDelete(row)">🗑️</button>
                  </div>
                </li>
              </ul>
              <p v-if="!group.items.length" class="category-empty-hint">暂无课室，点击「+ 课室」添加小类</p>
            </article>
          </div>
          <p v-else class="empty-hint">暂无课室与课室负责人映射</p>
        </section>
        </div>

      <!-- OQC editors -->
      <div v-if="oqcDefectEditorOpen" class="modal-backdrop" @mousedown.self="closeOqcDefectEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ oqcDefectDialogTitle }}</h3>
            <button type="button" class="icon-btn" @click="closeOqcDefectEditor">✕</button>
        </div>
          <form class="editor-body" @submit.prevent="saveOqcDefectEditor">
            <label v-if="oqcDefectIntent !== 'minor'" class="field">
              <span>{{ oqcDefectIntent === 'major-edit' ? '大类名称' : '大类' }}</span>
              <input
                v-model.trim="formOqcCategory"
                required
                list="oqc-category-options"
                placeholder="不良代码大类名称"
              />
              <datalist id="oqc-category-options">
                <option v-for="cat in oqcDefectCategories" :key="cat" :value="cat" />
              </datalist>
            </label>
            <label v-if="oqcDefectIntent === 'minor' || oqcDefectIntent === 'full'" class="field">
              <span>代码（小类）</span>
              <input v-model.trim="formOqcCode" required placeholder="不良代码" />
            </label>
            <label v-if="oqcDefectIntent === 'minor' || oqcDefectIntent === 'full'" class="field">
              <span>不良描述（现象）</span>
              <input v-model.trim="formOqcDesc" required placeholder="主表选代码自动带出" />
            </label>
            <p v-if="oqcEditorError" class="editor-error">{{ oqcEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeOqcDefectEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="oqcSaving">{{ oqcSaving ? "保存中…" : "保存" }}</button>
      </div>
          </form>
        </div>
        </div>

      <div v-if="oqcModelSectionEditorOpen" class="modal-backdrop" @mousedown.self="closeOqcModelSectionEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ oqcModelSectionDialogTitle }}</h3>
            <button type="button" class="icon-btn" @click="closeOqcModelSectionEditor">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveOqcModelSectionEditor">
            <label v-if="oqcModelSectionIntent !== 'minor'" class="field">
              <span>{{ oqcModelSectionIntent === 'major-edit' ? '课室名称（大类）' : '课室（大类）' }}</span>
              <input
                v-model.trim="formOqcSection"
                required
                list="oqc-section-options"
                placeholder="送检单位 / 课室"
              />
              <datalist id="oqc-section-options">
                <option v-for="s in oqcSectionNameOptions" :key="s" :value="s" />
              </datalist>
            </label>
            <label v-if="oqcModelSectionIntent === 'minor' || oqcModelSectionIntent === 'full'" class="field">
              <span>机种（小类）</span>
              <input v-model.trim="formOqcModel" required placeholder="系列 / 机种" />
            </label>
            <p v-if="oqcEditorError" class="editor-error">{{ oqcEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeOqcModelSectionEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="oqcSaving">{{ oqcSaving ? "保存中…" : "保存" }}</button>
            </div>
          </form>
        </div>
        </div>

      <div v-if="oqcOwnerBulkRenameOpen" class="modal-backdrop" @mousedown.self="closeOqcOwnerBulkRename">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>一键更换负责人</h3>
            <button type="button" class="icon-btn" @click="closeOqcOwnerBulkRename">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveOqcOwnerBulkRename">
            <p class="bulk-rename-hint">
              将第三页所有「原负责人」名下的机种，以及第四页同名的「课室负责人」，统一改为「新负责人」，并同步抽检明细中的确认者、课室负责人联动。
            </p>
            <label class="field">
              <span>原负责人</span>
              <input
                v-model.trim="formOqcBulkOldOwner"
                required
                list="oqc-owner-bulk-old"
                placeholder="离职或交接前的姓名"
              />
              <datalist id="oqc-owner-bulk-old">
                <option v-for="o in oqcOwnerNameOptions" :key="'old-' + o" :value="o" />
              </datalist>
            </label>
            <label class="field">
              <span>新负责人</span>
              <input
                v-model.trim="formOqcBulkNewOwner"
                required
                list="oqc-owner-bulk-new"
                placeholder="接任者姓名"
              />
              <datalist id="oqc-owner-bulk-new">
                <option v-for="o in oqcOwnerNameOptions" :key="'new-' + o" :value="o" />
              </datalist>
            </label>
            <p v-if="oqcOwnerBulkRenameCount > 0 || oqcOwnerBulkRenameSectionHeadCount > 0" class="bulk-rename-count">
              将更新第三页 <strong>{{ oqcOwnerBulkRenameCount }}</strong> 条机种映射
              <template v-if="oqcOwnerBulkRenameSectionHeadCount > 0">
                、第四页 <strong>{{ oqcOwnerBulkRenameSectionHeadCount }}</strong> 条课室负责人
    </template>
            </p>
            <p v-if="oqcEditorError" class="editor-error">{{ oqcEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeOqcOwnerBulkRename">取消</button>
              <button type="submit" class="primary-btn" :disabled="oqcSaving">
                {{ oqcSaving ? "保存中…" : "确认更换" }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div v-if="oqcModelOwnerEditorOpen" class="modal-backdrop" @mousedown.self="closeOqcModelOwnerEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ oqcModelOwnerDialogTitle }}</h3>
            <button type="button" class="icon-btn" @click="closeOqcModelOwnerEditor">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveOqcModelOwnerEditor">
            <label v-if="oqcModelOwnerIntent !== 'minor'" class="field">
              <span>负责人</span>
              <input
                v-model.trim="formOqcOwner"
                required
                list="oqc-owner-options"
                placeholder="负责人姓名"
              />
              <datalist id="oqc-owner-options">
                <option v-for="o in oqcOwnerNameOptions" :key="o" :value="o" />
              </datalist>
            </label>
            <label v-if="oqcModelOwnerIntent !== 'major'" class="field">
              <span>机种</span>
              <input v-model.trim="formOqcModel" required placeholder="机种 / 系列代码" />
            </label>
            <p v-if="oqcEditorError" class="editor-error">{{ oqcEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeOqcModelOwnerEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="oqcSaving">{{ oqcSaving ? "保存中…" : "保存" }}</button>
            </div>
          </form>
        </div>
      </div>

      <div v-if="oqcSectionHeadEditorOpen" class="modal-backdrop" @mousedown.self="closeOqcSectionHeadEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ oqcSectionHeadDialogTitle }}</h3>
            <button type="button" class="icon-btn" @click="closeOqcSectionHeadEditor">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveOqcSectionHeadEditor">
            <label v-if="oqcSectionHeadIntent !== 'minor'" class="field">
              <span>{{ oqcSectionHeadIntent === 'major-edit' ? '课室负责人名称（大类）' : '课室负责人（大类）' }}</span>
              <input
                v-model.trim="formOqcHead"
                required
                list="oqc-head-options"
                placeholder="负责人姓名"
              />
              <datalist id="oqc-head-options">
                <option v-for="h in oqcHeadNameOptions" :key="h" :value="h" />
              </datalist>
            </label>
            <label v-if="oqcSectionHeadIntent === 'minor' || oqcSectionHeadIntent === 'full'" class="field field-combo">
              <span>课室（小类 / 送检单位）</span>
              <ComboField
                v-model="formOqcSection"
                :options="oqcSectionNameOptions"
                placeholder="选择已有课室或输入新名称"
              />
              <p class="field-hint">可从第二页已有课室中选择，也可手动输入新送检单位</p>
            </label>
            <p v-if="oqcEditorError" class="editor-error">{{ oqcEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeOqcSectionHeadEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="oqcSaving">{{ oqcSaving ? "保存中…" : "保存" }}</button>
            </div>
          </form>
        </div>
      </div>
    </template>

    <template v-else-if="isInspectionLayout">
      <div class="rule-tabs">
        <button
          type="button"
          :class="{ on: ruleTab === 'classification' }"
          @click="ruleTab = 'classification'"
        >分类 ↔ 类别</button>
        <button
          type="button"
          :class="{ on: ruleTab === 'module' }"
          @click="ruleTab = 'module'"
        >模块 ↔ 负责人</button>
      </div>

      <div v-if="canEdit" class="toolbar">
        <template v-if="ruleTab === 'classification'">
          <button type="button" class="primary-btn" @click="openCreateCategory">添加类别</button>
          <button type="button" class="ghost-btn" @click="openCreate">添加分类</button>
        </template>
        <button
          v-if="ruleTab === 'module'"
          type="button"
          class="primary-btn"
          @click="openModuleCreate"
        >添加模块</button>
        <span v-if="syncHint" class="sync-hint">{{ syncHint }}</span>
      </div>

      <div v-show="ruleTab === 'classification'" class="category-overview">
        <p class="overview-summary">
          共 <strong>{{ categoryGroups.length }}</strong> 个类别、
          <strong>{{ totalClassifications }}</strong> 项分类
          <span class="overview-hint">· 问题录入时选「分类」自动带出「类别」</span>
        </p>
        <div class="category-search-bar">
          <input v-model.trim="categorySearch" type="search" placeholder="搜索类别或分类名称…" />
          <button v-if="categorySearch" type="button" class="ghost-btn" @click="categorySearch = ''">清除</button>
          <span v-if="categorySearch" class="search-result-hint">匹配 {{ filteredCategoryGroups.length }} 个类别</span>
        </div>

        <div v-if="filteredCategoryGroups.length" class="category-grid">
          <article
            v-for="group in filteredCategoryGroups"
            :key="group.category"
            class="category-card"
            :class="group.className"
          >
            <header class="category-card-head">
              <h3>
                <i class="cat-dot" :class="group.className" />
                {{ group.category }}
              </h3>
              <span class="cat-count">{{ group.count }}</span>
              <button
                v-if="canEdit"
                type="button"
                class="card-add-btn"
                title="在此类别下添加分类"
                @click="openCreateForCategory(group.category)"
              >+ 分类</button>
            </header>
            <ul v-if="group.items.length" class="classification-list compact">
              <li
                v-for="row in group.items"
                :key="'cls-' + row.no + '-' + row.classification"
                class="classification-item"
                :class="group.className"
              >
                <span class="cls-index">{{ formatNo(row.no) }}</span>
                <span class="cls-name">{{ row.classification }}</span>
                <div v-if="canEdit" class="cls-actions">
                  <button type="button" class="icon-btn" title="编辑" @click="openEdit(row)">✏️</button>
                  <button type="button" class="icon-btn" title="删除" @click="confirmDelete(row)">🗑️</button>
                </div>
              </li>
            </ul>
            <p v-else class="category-empty-hint">暂无分类，点击「+ 分类」添加</p>
          </article>
        </div>
        <p v-else class="empty-hint">{{ categorySearch ? '没有匹配的类别或分类' : '暂无分类规则，请先添加类别' }}</p>
      </div>

      <div v-show="ruleTab === 'module'" class="module-grid-wrap">
        <div class="module-grid">
          <article
            v-for="row in inspectionModules"
            :key="'mod-' + row.no + '-' + row.module"
            class="module-card"
          >
            <div class="module-card-body">
              <div class="module-name">{{ row.module }}</div>
              <div class="module-owner">
                <span class="owner-label">负责人</span>
                <span>{{ row.owner }}</span>
              </div>
            </div>
            <div v-if="canEdit" class="module-card-actions">
              <button type="button" class="icon-btn" title="编辑" @click="openModuleEdit(row)">✏️</button>
              <button type="button" class="icon-btn" title="删除" @click="confirmModuleDelete(row)">🗑️</button>
            </div>
          </article>
        </div>
        <p v-if="!inspectionModules.length" class="empty-hint">暂无模块规则</p>
      </div>

      <div v-if="editorOpen" class="modal-backdrop" @mousedown.self="closeEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ classificationEditorTitle }}</h3>
            <button type="button" class="icon-btn" @click="closeEditor">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveEditor">
            <template v-if="createIntent === 'category' && !editingRow">
              <label class="field">
                <span>类别</span>
                <input
                  v-model.trim="formCategory"
                  type="text"
                  required
                  autofocus
                  placeholder="新类别名称，如 5S类"
                />
                <small class="field-hint">保存后可在此类别下添加具体分类</small>
              </label>
            </template>
            <template v-else>
              <label class="field">
                <span>类别</span>
                <input
                  v-model.trim="formCategory"
                  type="text"
                  required
                  list="category-options"
                  placeholder="选择或输入类别"
                  :readonly="createIntent === 'classification' && !!presetCategory"
                />
                <datalist id="category-options">
                  <option v-for="cat in categoryOptions" :key="cat" :value="cat" />
                </datalist>
              </label>
              <label class="field">
                <span>分类</span>
                <input v-model.trim="formClassification" type="text" required placeholder="问题分类名称" />
              </label>
            </template>
            <p v-if="editorError" class="editor-error">{{ editorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="saving">
                {{ saving ? "保存中…" : "保存" }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div v-if="moduleEditorOpen" class="modal-backdrop" @mousedown.self="closeModuleEditor">
        <div class="editor-dialog modal-panel">
          <div class="dialog-head">
            <h3>{{ editingModuleRow ? "编辑模块" : "添加模块" }}</h3>
            <button type="button" class="icon-btn" @click="closeModuleEditor">✕</button>
          </div>
          <form class="editor-body" @submit.prevent="saveModuleEditor">
            <label class="field">
              <span>模块</span>
              <input
                v-model.trim="formModule"
                type="text"
                required
                list="module-options"
                placeholder="模块名称"
                @input="onModuleInputChange"
              />
              <datalist id="module-options">
                <option v-for="mod in filteredModuleSuggestions" :key="mod" :value="mod" />
              </datalist>
            </label>
            <label class="field">
              <span>负责人</span>
              <input
                v-model.trim="formOwner"
                type="text"
                required
                list="owner-options"
                placeholder="可选择已有负责人，或直接输入新负责人"
                @input="onOwnerInputChange"
              />
              <datalist id="owner-options">
                <option v-for="owner in ownerOptions" :key="owner" :value="owner" />
              </datalist>
              <small class="field-hint">选择负责人后，若仅对应一个模块将自动填入；选择模块后自动带出负责人</small>
            </label>
            <p v-if="moduleEditorError" class="editor-error">{{ moduleEditorError }}</p>
            <div class="dialog-actions">
              <button type="button" class="ghost-btn" @click="closeModuleEditor">取消</button>
              <button type="submit" class="primary-btn" :disabled="moduleSaving">
                {{ moduleSaving ? "保存中…" : "保存" }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="generic-wrap">
        <table class="code-table">
          <thead>
            <tr>
              <th v-for="col in genericColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in genericRows" :key="idx">
              <td v-for="col in genericColumns" :key="col">{{ formatCell(row[col]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { authFetch } from "./api.js";
import ComboField from "./ComboField.vue";

const props = defineProps({
  workbookId: String,
  spec: Object,
  sheetName: { type: String, default: "代码" },
  canEdit: { type: Boolean, default: false },
});

const emit = defineEmits(["updated"]);

const loading = ref(false);
const error = ref("");
const rawRows = ref([]);
const classificationItems = ref([]);
const moduleItems = ref([]);
const categoryOptions = ref([]);
const ownerOptions = ref([]);
const moduleOptions = ref([]);
const moduleOwnersMap = ref({});
const ownerModulesMap = ref({});
const codeSheetResolved = ref("");
const editorOpen = ref(false);
const moduleEditorOpen = ref(false);
const editingRow = ref(null);
const editingModuleRow = ref(null);
const formClassification = ref("");
const formCategory = ref("");
const formModule = ref("");
const formOwner = ref("");
const editorError = ref("");
const moduleEditorError = ref("");
const saving = ref(false);
const moduleSaving = ref(false);
const syncHint = ref("");
const ruleTab = ref("classification");
const categorySearch = ref("");
const oqcPage = ref(1);
const createIntent = ref("classification");
const presetCategory = ref("");
const oqcDefects = ref([]);
const oqcModelSections = ref([]);
const oqcModelOwners = ref([]);
const oqcSectionHeads = ref([]);
const oqcDefectCategories = ref([]);
const oqcDefectEditorOpen = ref(false);
const oqcModelSectionEditorOpen = ref(false);
const oqcModelOwnerEditorOpen = ref(false);
const oqcSectionHeadEditorOpen = ref(false);
const editingOqcDefect = ref(null);
const editingOqcModelSection = ref(null);
const editingOqcModelOwner = ref(null);
const editingOqcSectionHead = ref(null);
const formOqcCode = ref("");
const formOqcDesc = ref("");
const formOqcCategory = ref("");
const formOqcModel = ref("");
const formOqcSection = ref("");
const formOqcOwner = ref("");
const formOqcHead = ref("");
const formOqcMajorOldName = ref("");
const oqcEditorError = ref("");
const oqcSaving = ref(false);
const layoutKind = ref("inspection");

const statusLegend = [
  { label: "OK", className: "ok", desc: "检验判定合格" },
  { label: "OK1", className: "ok1", desc: "免检" },
  { label: "OK2", className: "ok2", desc: "特采" },
  { label: "NG", className: "ng", desc: "检验判定不良" },
  { label: "[NG]", className: "ng-batch", desc: "同批有不良" },
];

const resolvedCodeSheetName = computed(() => {
  const sheets = props.spec?.sheets || [];
  const target = props.sheetName.trim();
  const exact = sheets.find((s) => (s.name || "").trim() === target);
  if (exact) return exact.name || props.sheetName;
  const lookup = sheets.find((s) => {
    const n = (s.name || "").trim();
    if (n !== "代码" && !n.includes("代码表")) return false;
    const keys = new Set((s.columns || []).map((c) => c.key));
    return keys.has("代码") && keys.has("不良描述");
  });
  return lookup?.name || props.sheetName;
});

const sheetSpec = computed(
  () =>
    (props.spec?.sheets || []).find(
      (s) => (s.name || "").trim() === resolvedCodeSheetName.value.trim(),
    ) || null,
);

const isOqcLayout = computed(() => {
  if (layoutKind.value === "oqc") return true;
  const keys = new Set((sheetSpec.value?.columns || []).map((c) => c.key));
  if (keys.has("代码") && keys.has("不良描述") && keys.has("大类")) return true;
  return keys.has("代码") && keys.has("不良描述") && keys.has("机种");
});

const isInspectionLayout = computed(() => {
  const keys = new Set((sheetSpec.value?.columns || []).map((c) => c.key));
  return (
    !isOqcLayout.value &&
    keys.has("分类") &&
    keys.has("类别") &&
    keys.has("模块") &&
    keys.has("负责人")
  );
});

const CATEGORY_COLORS = {
  标准书管理类: "cat-standard",
  不按标准作业: "cat-operation",
  状态标识类: "cat-status",
  点检类: "cat-inspection",
  错漏混: "cat-mix",
  抽检类: "cat-sampling",
  首检类: "cat-first",
  违反准入要求: "cat-access",
  静电管理类: "cat-esd",
  样品管理类: "cat-sample",
  仪器管理类: "cat-instrument",
  胶油管理类: "cat-glue",
  "5S类": "cat-5s",
};

function categoryRowClass(category) {
  const key = String(category || "").trim();
  return CATEGORY_COLORS[key] || "cat-default";
}

function isBlank(v) {
  if (v == null) return true;
  const s = String(v).trim();
  return !s || s === "-" || s === "－" || s.toLowerCase() === "nan";
}

function formatNo(v) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? String(Math.trunc(n)) : String(v);
}

function formatCell(v) {
  if (isBlank(v)) return "—";
  return String(v);
}

function collectPairs(rows, leftKey, rightKey, useLeftAsKey = true) {
  const map = new Map();
  for (const row of rows) {
    const left = row[leftKey];
    const right = row[rightKey];
    if (isBlank(left) || isBlank(right)) continue;
    const a = String(left).trim();
    const b = String(right).trim();
    if (useLeftAsKey) {
      map.set(a, b);
    } else if (!map.has(a)) {
      map.set(a, b);
    }
  }
  return [...map.entries()]
    .map(([a, b]) => ({ a, b }))
    .sort((x, y) => x.a.localeCompare(y.a, "zh-CN"));
}

const tables = computed(() => {
  const defects = [];
  const seenCodes = new Set();

  for (const row of rawRows.value) {
    const code = row["代码"];
    if (isBlank(code)) continue;
    const key = String(code).trim();
    if (seenCodes.has(key)) continue;
    seenCodes.add(key);
    defects.push({
      no: row["NO."] ?? row["序号"],
      code: key,
      desc: row["不良描述"],
      category: row["大类"],
    });
  }

  defects.sort((a, b) => (Number(a.no) || 0) - (Number(b.no) || 0));

  const modelSection = collectPairs(rawRows.value, "机种", "课室").map(({ a, b }) => ({
    model: a,
    section: b,
  }));

  const modelOwner = collectPairs(rawRows.value, "机种_2", "负责人").map(({ a, b }) => ({
    model: a,
    owner: b,
  }));
  if (!modelOwner.length) {
    collectPairs(rawRows.value, "机种", "负责人").forEach(({ a, b }) => {
      if (!modelOwner.some((r) => r.model === a)) modelOwner.push({ model: a, owner: b });
    });
    modelOwner.sort((x, y) => x.model.localeCompare(y.model, "zh-CN"));
  }

  const sectionHead = extractSectionHeadsFromRows(rawRows.value);

  return { defects, modelSection, modelOwner, sectionHead };
});

const OQC_SECTION_SORT = ["变焦一课", "变焦二课", "变焦三课", "试做课", "红外", "消费三课"];

function sortOqcSectionHeads(items) {
  const order = new Map(OQC_SECTION_SORT.map((name, idx) => [name, idx]));
  return [...items].sort((a, b) => {
    const ai = order.has(a.section) ? order.get(a.section) : 999;
    const bi = order.has(b.section) ? order.get(b.section) : 999;
    if (ai !== bi) return ai - bi;
    return String(a.section).localeCompare(String(b.section), "zh-CN");
  });
}

function extractSectionHeadsFromRows(rows) {
  const items = [];
  const seen = new Set();
  for (const row of rows) {
    const head = row["课室负责人"];
    if (isBlank(head)) continue;
    let section = row["课室_2"];
    if (isBlank(section)) {
      if (!isBlank(row["机种"])) continue;
      section = row["课室"];
    }
    if (isBlank(section)) continue;
    const key = String(section).trim();
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({
      section: key,
      head: String(head).trim(),
      no: row["NO."] ?? row["序号"] ?? null,
    });
  }
  return sortOqcSectionHeads(items);
}

function extractModelOwnersFromRows(rows) {
  const items = [];
  const seen = new Set();
  for (const row of rows) {
    const owner = row["负责人"];
    if (isBlank(owner)) continue;
    let model = row["机种_2"];
    if (isBlank(model)) model = row["机种"];
    if (isBlank(model)) continue;
    const key = String(model).trim();
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({
      model: key,
      owner: String(owner).trim(),
      no: row["NO."] ?? row["序号"] ?? null,
    });
  }
  return items.sort((a, b) => a.model.localeCompare(b.model, "zh-CN"));
}

const oqcSectionHeadsDisplay = computed(() => {
  if (oqcSectionHeads.value.length) return sortOqcSectionHeads(oqcSectionHeads.value);
  return tables.value.sectionHead.length
    ? sortOqcSectionHeads(
        tables.value.sectionHead.map((r) => ({ section: r.section, head: r.head, no: null })),
      )
    : [];
});

const oqcModelOwnersDisplay = computed(() => {
  if (oqcModelOwners.value.length) return oqcModelOwners.value;
  if (tables.value.modelOwner.length) {
    return tables.value.modelOwner.map((r) => ({ model: r.model, owner: r.owner, no: null }));
  }
  return extractModelOwnersFromRows(rawRows.value);
});

function extractModelSectionsFromRows(rows) {
  const items = [];
  const seen = new Set();
  for (const row of rows) {
    const model = row["机种"];
    const section = row["课室"];
    if (isBlank(model) || isBlank(section)) continue;
    const key = String(model).trim();
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({
      model: key,
      section: String(section).trim(),
      no: row["NO."] ?? row["序号"] ?? null,
    });
  }
  return items.sort((a, b) => a.model.localeCompare(b.model, "zh-CN"));
}

const oqcModelSectionsDisplay = computed(() => {
  if (oqcModelSections.value.length) return oqcModelSections.value;
  if (tables.value.modelSection.length) {
    return tables.value.modelSection.map((r) => ({ model: r.model, section: r.section, no: null }));
  }
  return extractModelSectionsFromRows(rawRows.value);
});

function groupOqcByCategory(rows, categoryField, className) {
  const map = new Map();
  for (const row of rows) {
    const category = String(row[categoryField] || "").trim();
    if (!category) continue;
    if (!map.has(category)) map.set(category, []);
    map.get(category).push(row);
  }
  return [...map.entries()]
    .map(([category, items]) => ({
      category,
      items: [...items].sort((a, b) => String(a.model || a.section).localeCompare(String(b.model || b.section), "zh-CN")),
      count: items.length,
      className,
    }))
    .sort((a, b) => a.category.localeCompare(b.category, "zh-CN"));
}

function sortOqcSectionGroups(groups) {
  const order = new Map(OQC_SECTION_SORT.map((name, idx) => [name, idx]));
  return [...groups].sort((a, b) => {
    const ai = order.has(a.category) ? order.get(a.category) : 999;
    const bi = order.has(b.category) ? order.get(b.category) : 999;
    if (ai !== bi) return ai - bi;
    return a.category.localeCompare(b.category, "zh-CN");
  });
}

const oqcModelSectionIntent = ref("full");
const oqcModelOwnerIntent = ref("full");

const oqcModelSectionDialogTitle = computed(() => {
  if (oqcModelSectionIntent.value === "major-edit") return "编辑课室（大类）";
  if (editingOqcModelSection.value) return "编辑机种（小类）";
  if (oqcModelSectionIntent.value === "major") return "添加课室（大类）";
  if (oqcModelSectionIntent.value === "minor") return "添加机种（小类）";
  return "添加机种 · 课室";
});

const oqcModelOwnerDialogTitle = computed(() => {
  if (editingOqcModelOwner.value) return "编辑机种 · 负责人";
  if (oqcModelOwnerIntent.value === "major") return "添加负责人";
  if (oqcModelOwnerIntent.value === "minor") return "添加机种";
  return "添加机种 · 负责人";
});

const oqcModelOwnerFilterModel = ref("");
const oqcModelOwnerFilterOwner = ref("");
const oqcOwnerBulkRenameOpen = ref(false);
const formOqcBulkOldOwner = ref("");
const formOqcBulkNewOwner = ref("");

const oqcOwnerBulkRenameCount = computed(() => {
  const oldName = formOqcBulkOldOwner.value.trim();
  if (!oldName) return 0;
  return oqcModelOwnersDisplay.value.filter((r) => String(r.owner || "").trim() === oldName).length;
});

const oqcOwnerBulkRenameSectionHeadCount = computed(() => {
  const oldName = formOqcBulkOldOwner.value.trim();
  if (!oldName) return 0;
  return oqcSectionHeadsDisplay.value.filter((r) => String(r.head || "").trim() === oldName).length;
});

const oqcModelOwnerFilterModelOptions = computed(() => {
  const fo = oqcModelOwnerFilterOwner.value.trim();
  let rows = oqcModelOwnersDisplay.value;
  if (fo) rows = rows.filter((r) => String(r.owner || "").trim() === fo);
  const set = new Set();
  for (const r of rows) {
    const m = String(r.model || "").trim();
    if (m) set.add(m);
  }
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const oqcModelOwnerFilterOwnerOptions = computed(() => {
  const fm = oqcModelOwnerFilterModel.value.trim();
  let rows = oqcModelOwnersDisplay.value;
  if (fm) rows = rows.filter((r) => String(r.model || "").trim() === fm);
  const set = new Set();
  for (const r of rows) {
    const o = String(r.owner || "").trim();
    if (o) set.add(o);
  }
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const oqcModelOwnerTableRows = computed(() => {
  let rows = [...oqcModelOwnersDisplay.value].sort((a, b) =>
    String(a.model || "").localeCompare(String(b.model || ""), "zh-CN"),
  );
  const fm = oqcModelOwnerFilterModel.value.trim();
  const fo = oqcModelOwnerFilterOwner.value.trim();
  if (fm) rows = rows.filter((r) => String(r.model || "").trim() === fm);
  if (fo) rows = rows.filter((r) => String(r.owner || "").trim() === fo);
  return rows;
});

const oqcSectionHeadIntent = ref("full");

const oqcSectionHeadDialogTitle = computed(() => {
  if (oqcSectionHeadIntent.value === "major-edit") return "编辑课室负责人（大类）";
  if (editingOqcSectionHead.value) return "编辑课室（小类）";
  if (oqcSectionHeadIntent.value === "major") return "添加课室负责人（大类）";
  if (oqcSectionHeadIntent.value === "minor") return "添加课室（小类）";
  return "添加课室 · 课室负责人";
});

const oqcModelSectionGroupsCore = computed(() => {
  const groups = groupOqcByCategory(oqcModelSectionsDisplay.value, "section", "cat-oqc-section");
  const seen = new Set(groups.map((g) => g.category));
  for (const row of rawRows.value) {
    const sec = String(row["课室"] || "").trim();
    if (!sec || seen.has(sec)) continue;
    seen.add(sec);
    groups.push({ category: sec, items: [], count: 0, className: "cat-oqc-section" });
  }
  return groups;
});

const oqcModelSectionGroups = computed(() => sortOqcSectionGroups(oqcModelSectionGroupsCore.value));

const oqcSectionNameOptions = computed(() => {
  const set = new Set();
  for (const g of oqcModelSectionGroupsCore.value) set.add(g.category);
  for (const r of oqcSectionHeadsDisplay.value) set.add(r.section);
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const oqcOwnerNameOptions = computed(() => {
  const set = new Set();
  for (const r of oqcModelOwnersDisplay.value) {
    const name = String(r.owner || "").trim();
    if (name) set.add(name);
  }
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const oqcHeadNameOptions = computed(() => {
  const set = new Set();
  for (const g of oqcSectionHeadGroupsCore.value) set.add(g.category);
  return [...set].sort((a, b) => a.localeCompare(b, "zh-CN"));
});

const oqcSectionHeadGroupsCore = computed(() => {
  const groups = groupOqcByCategory(oqcSectionHeadsDisplay.value, "head", "cat-oqc-section");
  const seen = new Set(groups.map((g) => g.category));
  for (const row of rawRows.value) {
    const head = String(row["课室负责人"] || "").trim();
    if (!head || seen.has(head)) continue;
    const section = row["课室_2"] ?? row["课室"];
    if (!isBlank(section) || !isBlank(row["机种"])) continue;
    seen.add(head);
    groups.push({ category: head, items: [], count: 0, className: "cat-oqc-section" });
  }
  return groups;
});

const oqcSectionHeadGroups = computed(() =>
  [...oqcSectionHeadGroupsCore.value].sort((a, b) => a.category.localeCompare(b.category, "zh-CN")),
);

const inspectionTables = computed(() => {
  const classifications = [];
  const seenClass = new Set();

  for (const row of rawRows.value) {
    const classification = row["分类"];
    const category = row["类别"];
    if (isBlank(classification) || isBlank(category)) continue;
    const cls = String(classification).trim();
    const cat = String(category).trim();
    const dedupeKey = `${cls}::${cat}`;
    if (seenClass.has(dedupeKey)) continue;
    seenClass.add(dedupeKey);
    classifications.push({
      no: row["序号"],
      classification: cls,
      category: cat,
    });
  }

  classifications.sort((a, b) => (Number(a.no) || 0) - (Number(b.no) || 0));

  const moduleOwners = collectPairs(rawRows.value, "模块", "负责人").map(({ a, b }) => ({
    module: a,
    owner: b,
  }));

  return { classifications, moduleOwners };
});

const inspectionClassifications = computed(() => {
  if (classificationItems.value.length) return classificationItems.value;
  return inspectionTables.value.classifications;
});

const inspectionModules = computed(() => {
  if (moduleItems.value.length) return moduleItems.value;
  return inspectionTables.value.moduleOwners.map(({ module, owner }) => ({ module, owner, no: null }));
});

const categoryGroups = computed(() => {
  const map = new Map();
  for (const cat of categoryOptions.value) {
    const category = String(cat || "").trim();
    if (category && !map.has(category)) map.set(category, []);
  }
  for (const row of inspectionClassifications.value) {
    const category = String(row.category || "").trim();
    if (!category) continue;
    if (!map.has(category)) map.set(category, []);
    map.get(category).push(row);
  }
  return [...map.entries()]
    .map(([category, items]) => ({
      category,
      items,
      count: items.length,
      className: categoryRowClass(category),
    }))
    .sort((a, b) => a.category.localeCompare(b.category, "zh-CN"));
});

const totalClassifications = computed(() => inspectionClassifications.value.length);

const filteredCategoryGroups = computed(() => {
  const query = categorySearch.value.trim().toLocaleLowerCase();
  if (!query) return categoryGroups.value;
  return categoryGroups.value
    .map((group) => {
      const categoryMatches = String(group.category).toLocaleLowerCase().includes(query);
      return {
        ...group,
        items: categoryMatches
          ? group.items
          : group.items.filter((row) => String(row.classification || "").toLocaleLowerCase().includes(query)),
      };
    })
    .filter((group) =>
      String(group.category).toLocaleLowerCase().includes(query) || group.items.length,
    )
    .map((group) => ({ ...group, count: group.items.length }));
});

const classificationEditorTitle = computed(() => {
  if (editingRow.value) return "编辑分类";
  return createIntent.value === "category" ? "添加类别" : "添加分类";
});

const oqcDefectIntent = ref("full");

const oqcDefectDialogTitle = computed(() => {
  if (oqcDefectIntent.value === "major-edit") return "编辑大类";
  if (editingOqcDefect.value) return "编辑不良代码（小类）";
  if (oqcDefectIntent.value === "major") return "添加大类";
  if (oqcDefectIntent.value === "minor") return "添加代码（小类）";
  return "添加不良代码";
});

const oqcDefectCategoryGroups = computed(() => {
  const map = new Map();
  for (const cat of oqcDefectCategories.value) {
    const category = String(cat || "").trim();
    if (category && !map.has(category)) map.set(category, []);
  }
  const source = oqcDefects.value.length ? oqcDefects.value : tables.value.defects;
  for (const row of source) {
    const category = String(row.category || "").trim();
    if (!category) continue;
    if (!map.has(category)) map.set(category, []);
    map.get(category).push(row);
  }
  for (const row of rawRows.value) {
    const category = String(row["大类"] || "").trim();
    if (!category || map.has(category)) continue;
    if (isBlank(row["代码"])) {
      map.set(category, []);
    }
  }
  return [...map.entries()]
    .map(([category, items]) => ({
      category,
      items,
      count: items.length,
      className: categoryRowClass(category),
    }))
    .sort((a, b) => a.category.localeCompare(b.category, "zh-CN"));
});

const totalOqcDefects = computed(() => {
  const source = oqcDefects.value.length ? oqcDefects.value : tables.value.defects;
  return source.length;
});

const filteredModuleSuggestions = computed(() => {
  const owner = formOwner.value.trim();
  if (owner && ownerModulesMap.value[owner]?.length) {
    return ownerModulesMap.value[owner];
  }
  return moduleOptions.value;
});

function normalizeOqcCategoryOptions(categories, defects) {
  if (Array.isArray(categories)) return categories;
  if (categories && typeof categories === "object") {
    return [...new Set(Object.values(categories).map((c) => String(c || "").trim()).filter(Boolean))].sort(
      (a, b) => a.localeCompare(b, "zh-CN"),
    );
  }
  const fromDefects = new Set();
  for (const d of defects || []) {
    const c = String(d?.category || "").trim();
    if (c) fromDefects.add(c);
  }
  return [...fromDefects].sort((a, b) => a.localeCompare(b, "zh-CN"));
}

function normalizeOqcSectionHeadRows(sectionHeads) {
  if (Array.isArray(sectionHeads)) return sectionHeads;
  return [];
}

function applyOqcPayload(data, { emitUpdate = false } = {}) {
  layoutKind.value = "oqc";
  oqcDefects.value = data.defects || [];
  oqcModelSections.value = data.model_sections || [];
  oqcModelOwners.value = data.model_owners || [];
  oqcSectionHeads.value = normalizeOqcSectionHeadRows(data.section_heads);
  oqcDefectCategories.value = normalizeOqcCategoryOptions(data.defect_categories, data.defects);
  codeSheetResolved.value = data.code_sheet || props.sheetName;
  if (emitUpdate) {
    const sync = data.sync || {};
    const br = data.bulk_rename;
    const renameParts = [];
    if (br?.updated_rows) renameParts.push(`第三页机种 ${br.updated_rows} 条`);
    if (br?.updated_section_heads) renameParts.push(`第四页课室负责人 ${br.updated_section_heads} 条`);
    if (sync.synced) {
      const syncLine = sync.updated_rows
        ? `已同步抽检明细 ${sync.updated_rows} 行，并更新录入下拉与联动字段`
        : "已更新抽检明细录入下拉与 VLOOKUP 联动";
      syncHint.value = renameParts.length ? `${renameParts.join("、")}；${syncLine}` : syncLine;
    } else if (renameParts.length) {
      syncHint.value = `已更换：${renameParts.join("、")}`;
    } else {
      syncHint.value = "";
    }
    emit("updated", data);
  } else {
    syncHint.value = "";
  }
}

async function oqcPersist(data) {
  applyOqcPayload(data, { emitUpdate: true });
  await loadRawRows();
}

function applyCodeTablePayload(data, { emitUpdate = false } = {}) {
  layoutKind.value = data.layout || "inspection";
  classificationItems.value = data.items || [];
  moduleItems.value = data.modules || [];
  categoryOptions.value = data.category_options || [];
  ownerOptions.value = data.owner_options || [];
  moduleOptions.value = data.module_options || [];
  moduleOwnersMap.value = data.module_owners || {};
  ownerModulesMap.value = data.owner_modules || {};
  codeSheetResolved.value = data.code_sheet || props.sheetName;
  if (emitUpdate) {
    const parts = [];
    const sync = data.sync || {};
    if (sync.updated_category_rows > 0) parts.push(`类别 ${sync.updated_category_rows} 行`);
    if (sync.updated_module_rows > 0) parts.push(`工段负责人 ${sync.updated_module_rows} 行`);
    syncHint.value = parts.length ? `已同步更新问题清单：${parts.join("、")}` : "";
  } else {
    syncHint.value = "";
  }
  if (emitUpdate) emit("updated", data);
}

function openCreateCategory() {
  editingRow.value = null;
  createIntent.value = "category";
  presetCategory.value = "";
  formClassification.value = "";
  formCategory.value = "";
  editorError.value = "";
  editorOpen.value = true;
}

function openCreate() {
  openCreateForCategory("");
}

function openCreateForCategory(category) {
  editingRow.value = null;
  createIntent.value = "classification";
  presetCategory.value = category || "";
  formClassification.value = "";
  formCategory.value = category || "";
  editorError.value = "";
  editorOpen.value = true;
}

function openEdit(row) {
  editingRow.value = row;
  createIntent.value = "classification";
  presetCategory.value = "";
  formClassification.value = row.classification;
  formCategory.value = row.category;
  editorError.value = "";
  editorOpen.value = true;
}

function closeEditor() {
  editorOpen.value = false;
  editingRow.value = null;
  presetCategory.value = "";
  editorError.value = "";
}

async function saveEditor() {
  if (!props.workbookId || saving.value) return;
  saving.value = true;
  editorError.value = "";
  try {
    if (createIntent.value === "category" && !editingRow.value) {
      const res = await authFetch(`/api/workbooks/${props.workbookId}/code-categories`, {
        method: "POST",
        body: JSON.stringify({
          code_sheet: codeSheetResolved.value || props.sheetName,
          category: formCategory.value,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "保存失败");
      applyCodeTablePayload(data, { emitUpdate: true });
      closeEditor();
      await loadRawRows();
      return;
    }

    const body = {
      code_sheet: codeSheetResolved.value || props.sheetName,
      classification: formClassification.value,
      category: formCategory.value,
    };
    let res;
    if (editingRow.value) {
      body.old_classification = editingRow.value.classification;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/code-classifications/${encodeURIComponent(editingRow.value.no)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/code-classifications`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    applyCodeTablePayload(data, { emitUpdate: true });
    closeEditor();
    await loadRawRows();
  } catch (err) {
    editorError.value = String(err.message || err);
  } finally {
    saving.value = false;
  }
}

function openModuleCreate() {
  editingModuleRow.value = null;
  formModule.value = "";
  formOwner.value = "";
  moduleEditorError.value = "";
  moduleEditorOpen.value = true;
}

function openModuleEdit(row) {
  editingModuleRow.value = row;
  formModule.value = row.module;
  formOwner.value = row.owner;
  moduleEditorError.value = "";
  moduleEditorOpen.value = true;
}

function closeModuleEditor() {
  moduleEditorOpen.value = false;
  editingModuleRow.value = null;
  moduleEditorError.value = "";
}

function onModuleInputChange() {
  const mod = formModule.value.trim();
  if (mod && moduleOwnersMap.value[mod]) {
    formOwner.value = moduleOwnersMap.value[mod];
  }
}

function onOwnerInputChange() {
  const owner = formOwner.value.trim();
  if (!owner) return;
  const mods = ownerModulesMap.value[owner] || [];
  if (mods.length === 1) {
    formModule.value = mods[0];
  } else if (mods.length > 1 && formModule.value && !mods.includes(formModule.value)) {
    formModule.value = "";
  }
}

function mergeLocalOwnerModule(module, owner) {
  if (!module || !owner) return;
  moduleOwnersMap.value = { ...moduleOwnersMap.value, [module]: owner };
  const prev = ownerModulesMap.value[owner] || [];
  if (!prev.includes(module)) {
    ownerModulesMap.value = { ...ownerModulesMap.value, [owner]: [...prev, module].sort() };
  }
  if (!ownerOptions.value.includes(owner)) {
    ownerOptions.value = [...ownerOptions.value, owner].sort((a, b) => a.localeCompare(b, "zh-CN"));
  }
  if (!moduleOptions.value.includes(module)) {
    moduleOptions.value = [...moduleOptions.value, module].sort((a, b) => a.localeCompare(b, "zh-CN"));
  }
}

async function saveModuleEditor() {
  if (!props.workbookId || moduleSaving.value) return;
  moduleSaving.value = true;
  moduleEditorError.value = "";
  try {
    const body = {
      code_sheet: codeSheetResolved.value || props.sheetName,
      module: formModule.value,
      owner: formOwner.value,
    };
    let res;
    if (editingModuleRow.value?.no != null) {
      body.old_module = editingModuleRow.value.module;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/code-modules/${encodeURIComponent(editingModuleRow.value.no)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/code-modules`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    mergeLocalOwnerModule(formModule.value, formOwner.value);
    applyCodeTablePayload(data, { emitUpdate: true });
    closeModuleEditor();
    await loadRawRows();
  } catch (err) {
    moduleEditorError.value = String(err.message || err);
  } finally {
    moduleSaving.value = false;
  }
}

async function confirmModuleDelete(row) {
  if (!props.workbookId) return;
  if (!window.confirm(`确定删除模块「${row.module}」？\n若问题清单中已引用该模块将无法删除。`)) return;
  try {
    const params = new URLSearchParams();
    if (codeSheetResolved.value) params.set("code_sheet", codeSheetResolved.value);
    params.set("module", row.module);
    const id = row.no != null ? row.no : row.module;
    const res = await authFetch(
      `/api/workbooks/${props.workbookId}/code-modules/${encodeURIComponent(id)}?${params}`,
      { method: "DELETE" },
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "删除失败");
    applyCodeTablePayload(data, { emitUpdate: true });
    await loadRawRows();
  } catch (err) {
    alert(String(err.message || err));
  }
}

async function confirmDelete(row) {
  if (!props.workbookId) return;
  if (!window.confirm(`确定删除分类「${row.classification}」？\n若问题清单中已引用该分类将无法删除。`)) return;
  try {
    const params = new URLSearchParams();
    if (codeSheetResolved.value) params.set("code_sheet", codeSheetResolved.value);
    params.set("classification", row.classification);
    const res = await authFetch(
      `/api/workbooks/${props.workbookId}/code-classifications/${encodeURIComponent(row.no)}?${params}`,
      { method: "DELETE" },
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "删除失败");
    applyCodeTablePayload(data, { emitUpdate: true });
    await loadRawRows();
  } catch (err) {
    alert(String(err.message || err));
  }
}

async function loadClassifications() {
  if (!props.workbookId) return;
  const params = new URLSearchParams();
  if (resolvedCodeSheetName.value) params.set("code_sheet", resolvedCodeSheetName.value);
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/code-classifications?${params}`,
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "加载分类失败");
  if (data.layout === "oqc") {
    applyOqcPayload(data);
  } else {
    applyCodeTablePayload(data);
  }
}

function oqcBody(extra = {}) {
  return { code_sheet: codeSheetResolved.value || props.sheetName, ...extra };
}

function openOqcDefectMajorCreate() {
  editingOqcDefect.value = null;
  oqcDefectIntent.value = "major";
  formOqcCode.value = "";
  formOqcDesc.value = "";
  formOqcCategory.value = "";
  oqcEditorError.value = "";
  oqcDefectEditorOpen.value = true;
}

function openOqcDefectCreateForCategory(category) {
  editingOqcDefect.value = null;
  oqcDefectIntent.value = "minor";
  formOqcCode.value = "";
  formOqcDesc.value = "";
  formOqcCategory.value = category || "";
  oqcEditorError.value = "";
  oqcDefectEditorOpen.value = true;
}

function openOqcDefectEdit(row) {
  editingOqcDefect.value = row;
  oqcDefectIntent.value = "full";
  formOqcCode.value = row.code;
  formOqcDesc.value = row.desc;
  formOqcCategory.value = row.category;
  oqcEditorError.value = "";
  oqcDefectEditorOpen.value = true;
}

function closeOqcDefectEditor() {
  oqcDefectEditorOpen.value = false;
  editingOqcDefect.value = null;
  oqcDefectIntent.value = "full";
  formOqcMajorOldName.value = "";
  oqcEditorError.value = "";
}

function openOqcDefectMajorEdit(category) {
  editingOqcDefect.value = null;
  oqcDefectIntent.value = "major-edit";
  formOqcMajorOldName.value = category || "";
  formOqcCategory.value = category || "";
  formOqcCode.value = "";
  formOqcDesc.value = "";
  oqcEditorError.value = "";
  oqcDefectEditorOpen.value = true;
}

async function confirmOqcDefectMajorDelete(group) {
  const name = group.category;
  const n = group.count || 0;
  const msg = n
    ? `确定删除大类「${name}」及其下 ${n} 项不良代码？\n若代码已被抽检明细引用将无法删除。`
    : `确定删除大类「${name}」？`;
  if (!window.confirm(msg)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-defect-categories?category=${encodeURIComponent(name)}&code_sheet=${encodeURIComponent(codeSheetResolved.value || props.sheetName)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

async function saveOqcDefectEditor() {
  if (!props.workbookId || oqcSaving.value) return;
  oqcSaving.value = true;
  oqcEditorError.value = "";
  try {
    let res;
    if (oqcDefectIntent.value === "major-edit") {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-defect-categories`, {
        method: "PUT",
        body: JSON.stringify(
          oqcBody({
            old_category: formOqcMajorOldName.value,
            category: formOqcCategory.value,
          }),
        ),
      });
    } else {
    const body = oqcBody({
      category: formOqcCategory.value,
      code: oqcDefectIntent.value === "major" ? null : formOqcCode.value,
      desc: oqcDefectIntent.value === "major" ? null : formOqcDesc.value,
    });
    if (editingOqcDefect.value) {
      body.old_code = editingOqcDefect.value.code;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/oqc-defects/${encodeURIComponent(editingOqcDefect.value.code)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-defects`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    await oqcPersist(data);
    closeOqcDefectEditor();
  } catch (err) {
    oqcEditorError.value = String(err.message || err);
  } finally {
    oqcSaving.value = false;
  }
}

async function confirmOqcDefectDelete(row) {
  if (!window.confirm(`确定删除不良代码「${row.code}」？`)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-defects/${encodeURIComponent(row.code)}?code_sheet=${encodeURIComponent(codeSheetResolved.value || props.sheetName)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

function openOqcSectionMajorCreate() {
  editingOqcModelSection.value = null;
  oqcModelSectionIntent.value = "major";
  formOqcModel.value = "";
  formOqcSection.value = "";
  oqcEditorError.value = "";
  oqcModelSectionEditorOpen.value = true;
}

function openOqcModelSectionCreateForCategory(section) {
  editingOqcModelSection.value = null;
  oqcModelSectionIntent.value = "minor";
  formOqcModel.value = "";
  formOqcSection.value = section || "";
  oqcEditorError.value = "";
  oqcModelSectionEditorOpen.value = true;
}

function openOqcModelSectionEdit(row) {
  editingOqcModelSection.value = row;
  oqcModelSectionIntent.value = "full";
  formOqcModel.value = row.model;
  formOqcSection.value = row.section;
  oqcEditorError.value = "";
  oqcModelSectionEditorOpen.value = true;
}

function closeOqcModelSectionEditor() {
  oqcModelSectionEditorOpen.value = false;
  editingOqcModelSection.value = null;
  oqcModelSectionIntent.value = "full";
  formOqcMajorOldName.value = "";
}

function openOqcClassroomMajorEdit(section) {
  editingOqcModelSection.value = null;
  oqcModelSectionIntent.value = "major-edit";
  formOqcMajorOldName.value = section || "";
  formOqcSection.value = section || "";
  formOqcModel.value = "";
  oqcEditorError.value = "";
  oqcModelSectionEditorOpen.value = true;
}

async function confirmOqcClassroomMajorDelete(group) {
  const name = group.category;
  const n = group.count || 0;
  const msg = n
    ? `确定删除课室「${name}」及其下 ${n} 个机种映射？\n若机种已被主表引用将无法删除。`
    : `确定删除课室「${name}」？`;
  if (!window.confirm(msg)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-classroom-groups?section=${encodeURIComponent(name)}&code_sheet=${encodeURIComponent(codeSheetResolved.value || props.sheetName)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

async function saveOqcModelSectionEditor() {
  if (!props.workbookId || oqcSaving.value) return;
  oqcSaving.value = true;
  oqcEditorError.value = "";
  try {
    let res;
    if (oqcModelSectionIntent.value === "major-edit") {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-classroom-groups`, {
        method: "PUT",
        body: JSON.stringify(
          oqcBody({
            old_section: formOqcMajorOldName.value,
            section: formOqcSection.value,
          }),
        ),
      });
    } else {
    const body = oqcBody({
      section: formOqcSection.value,
      model: oqcModelSectionIntent.value === "major" ? null : formOqcModel.value,
    });
    if (editingOqcModelSection.value) {
      body.old_model = editingOqcModelSection.value.model;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/oqc-model-sections/${encodeURIComponent(editingOqcModelSection.value.model)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-model-sections`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    await oqcPersist(data);
    closeOqcModelSectionEditor();
  } catch (err) {
    oqcEditorError.value = String(err.message || err);
  } finally {
    oqcSaving.value = false;
  }
}

async function confirmOqcModelSectionDelete(row) {
  if (!window.confirm(`确定删除机种「${row.model}」的送检单位映射？`)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-model-sections/${encodeURIComponent(row.model)}?code_sheet=${encodeURIComponent(codeSheetResolved.value || props.sheetName)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

function openOqcModelOwnerCreate() {
  editingOqcModelOwner.value = null;
  oqcModelOwnerIntent.value = "full";
  formOqcModel.value = "";
  formOqcOwner.value = "";
  oqcEditorError.value = "";
  oqcModelOwnerEditorOpen.value = true;
}

function clearOqcModelOwnerFilters() {
  oqcModelOwnerFilterModel.value = "";
  oqcModelOwnerFilterOwner.value = "";
}

function openOqcOwnerBulkRename() {
  formOqcBulkOldOwner.value = oqcModelOwnerFilterOwner.value.trim();
  formOqcBulkNewOwner.value = "";
  oqcEditorError.value = "";
  oqcOwnerBulkRenameOpen.value = true;
}

function closeOqcOwnerBulkRename() {
  oqcOwnerBulkRenameOpen.value = false;
  formOqcBulkOldOwner.value = "";
  formOqcBulkNewOwner.value = "";
  oqcEditorError.value = "";
}

async function saveOqcOwnerBulkRename() {
  if (!props.workbookId || oqcSaving.value) return;
  const oldOwner = formOqcBulkOldOwner.value.trim();
  const newOwner = formOqcBulkNewOwner.value.trim();
  if (!oldOwner || !newOwner) {
    oqcEditorError.value = "请填写原负责人和新负责人";
    return;
  }
  if (oldOwner === newOwner) {
    oqcEditorError.value = "新负责人不能与原负责人相同";
    return;
  }
  const count = oqcOwnerBulkRenameCount.value;
  const headCount = oqcOwnerBulkRenameSectionHeadCount.value;
  if (count > 0 || headCount > 0) {
    const lines = [];
    if (count > 0) lines.push(`${count} 个机种（第三页）`);
    if (headCount > 0) lines.push(`${headCount} 条课室负责人（第四页）`);
    if (
      !window.confirm(
        `确定将「${oldOwner}」统一改为「${newOwner}」？\n将更新：${lines.join("、")}。\n抽检明细中确认者、课室负责人等联动字段也会同步。`,
      )
    ) {
      return;
    }
  }
  oqcSaving.value = true;
  oqcEditorError.value = "";
  try {
    const res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-model-owners/bulk-rename`, {
      method: "POST",
      body: JSON.stringify(
        oqcBody({ old_owner: oldOwner, new_owner: newOwner }),
      ),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "更换失败");
    await oqcPersist(data);
    closeOqcOwnerBulkRename();
    oqcModelOwnerFilterOwner.value = "";
  } catch (err) {
    oqcEditorError.value = String(err.message || err);
  } finally {
    oqcSaving.value = false;
  }
}

function openOqcOwnerMajorCreate() {
  editingOqcModelOwner.value = null;
  oqcModelOwnerIntent.value = "major";
  formOqcModel.value = "";
  formOqcOwner.value = "";
  oqcEditorError.value = "";
  oqcModelOwnerEditorOpen.value = true;
}

function openOqcModelOwnerCreateForCategory(owner) {
  editingOqcModelOwner.value = null;
  oqcModelOwnerIntent.value = "minor";
  formOqcModel.value = "";
  formOqcOwner.value = owner || "";
  oqcEditorError.value = "";
  oqcModelOwnerEditorOpen.value = true;
}

function openOqcModelOwnerEdit(row) {
  editingOqcModelOwner.value = row;
  oqcModelOwnerIntent.value = "full";
  formOqcModel.value = row.model;
  formOqcOwner.value = row.owner;
  oqcEditorError.value = "";
  oqcModelOwnerEditorOpen.value = true;
}

function closeOqcModelOwnerEditor() {
  oqcModelOwnerEditorOpen.value = false;
  editingOqcModelOwner.value = null;
  oqcModelOwnerIntent.value = "full";
}

async function saveOqcModelOwnerEditor() {
  if (!props.workbookId || oqcSaving.value) return;
  oqcSaving.value = true;
  oqcEditorError.value = "";
  try {
    const body = oqcBody({
      owner: formOqcOwner.value,
      model: oqcModelOwnerIntent.value === "major" ? null : formOqcModel.value,
    });
    let res;
    if (editingOqcModelOwner.value) {
      body.old_model = editingOqcModelOwner.value.model;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/oqc-model-owners/${encodeURIComponent(editingOqcModelOwner.value.model)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-model-owners`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    await oqcPersist(data);
    closeOqcModelOwnerEditor();
  } catch (err) {
    oqcEditorError.value = String(err.message || err);
  } finally {
    oqcSaving.value = false;
  }
}

async function confirmOqcModelOwnerDelete(row) {
  if (!window.confirm(`确定删除机种「${row.model}」的负责人映射？\n抽检明细中该系列的负责人将不再自动带出。`)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-model-owners/${encodeURIComponent(row.model)}?code_sheet=${encodeURIComponent(codeSheetResolved.value || resolvedCodeSheetName.value)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

function openOqcSectionHeadMajorCreate() {
  editingOqcSectionHead.value = null;
  oqcSectionHeadIntent.value = "major";
  formOqcSection.value = "";
  formOqcHead.value = "";
  oqcEditorError.value = "";
  oqcSectionHeadEditorOpen.value = true;
}

function openOqcSectionHeadCreateForCategory(head) {
  editingOqcSectionHead.value = null;
  oqcSectionHeadIntent.value = "minor";
  formOqcSection.value = "";
  formOqcHead.value = head || "";
  oqcEditorError.value = "";
  oqcSectionHeadEditorOpen.value = true;
}

function openOqcSectionHeadEdit(row) {
  editingOqcSectionHead.value = row;
  oqcSectionHeadIntent.value = "full";
  formOqcSection.value = row.section;
  formOqcHead.value = row.head;
  oqcEditorError.value = "";
  oqcSectionHeadEditorOpen.value = true;
}

function closeOqcSectionHeadEditor() {
  oqcSectionHeadEditorOpen.value = false;
  editingOqcSectionHead.value = null;
  oqcSectionHeadIntent.value = "full";
  formOqcMajorOldName.value = "";
}

function openOqcSectionHeadMajorEdit(head) {
  editingOqcSectionHead.value = null;
  oqcSectionHeadIntent.value = "major-edit";
  formOqcMajorOldName.value = head || "";
  formOqcHead.value = head || "";
  formOqcSection.value = "";
  oqcEditorError.value = "";
  oqcSectionHeadEditorOpen.value = true;
}

async function confirmOqcSectionHeadMajorDelete(group) {
  const name = group.category;
  const n = group.count || 0;
  const msg = n
    ? `确定删除课室负责人「${name}」及其下 ${n} 个课室？\n若课室已被抽检明细引用将无法删除。`
    : `确定删除课室负责人「${name}」？`;
  if (!window.confirm(msg)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-section-head-groups?head=${encodeURIComponent(name)}&code_sheet=${encodeURIComponent(codeSheetResolved.value || props.sheetName)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

async function saveOqcSectionHeadEditor() {
  if (!props.workbookId || oqcSaving.value) return;
  oqcSaving.value = true;
  oqcEditorError.value = "";
  try {
    let res;
    if (oqcSectionHeadIntent.value === "major-edit") {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-section-head-groups`, {
        method: "PUT",
        body: JSON.stringify(
          oqcBody({
            old_head: formOqcMajorOldName.value,
            head: formOqcHead.value,
          }),
        ),
      });
    } else {
    const body = oqcBody({
      head: formOqcHead.value,
      section: oqcSectionHeadIntent.value === "major" ? null : formOqcSection.value,
    });
    if (editingOqcSectionHead.value) {
      body.old_section = editingOqcSectionHead.value.section;
      res = await authFetch(
        `/api/workbooks/${props.workbookId}/oqc-section-heads/${encodeURIComponent(editingOqcSectionHead.value.section)}`,
        { method: "PUT", body: JSON.stringify(body) },
      );
    } else {
      res = await authFetch(`/api/workbooks/${props.workbookId}/oqc-section-heads`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    }
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "保存失败");
    await oqcPersist(data);
    closeOqcSectionHeadEditor();
  } catch (err) {
    oqcEditorError.value = String(err.message || err);
  } finally {
    oqcSaving.value = false;
  }
}

async function confirmOqcSectionHeadDelete(row) {
  if (!window.confirm(`确定删除课室「${row.section}」及其课室负责人映射？\n若抽检明细已引用该送检单位将无法删除。`)) return;
  const res = await authFetch(
    `/api/workbooks/${props.workbookId}/oqc-section-heads/${encodeURIComponent(row.section)}?code_sheet=${encodeURIComponent(codeSheetResolved.value || resolvedCodeSheetName.value)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  if (!res.ok) {
    alert(data.detail || "删除失败");
    return;
  }
  await oqcPersist(data);
}

async function loadRawRows() {
    const all = [];
    let offset = 0;
    const limit = 500;
    let total = Infinity;
    while (offset < total) {
      const res = await authFetch(`/api/workbooks/${props.workbookId}/query`, {
        method: "POST",
        body: JSON.stringify({
        sheet: codeSheetResolved.value || resolvedCodeSheetName.value,
          offset,
          limit,
          filters: {},
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "加载失败");
      total = data.total ?? 0;
      all.push(...(data.rows || []));
      offset += limit;
      if (!(data.rows || []).length) break;
    }
    rawRows.value = all;
}

const genericColumns = computed(() => {
  const cols = (sheetSpec.value?.columns || [])
    .filter((c) => c.role !== "empty" && c.fill > 0 && c.key && !String(c.key).startsWith("列"))
    .map((c) => c.key);
  if (cols.length) return cols;
  if (!rawRows.value.length) return [];
  return Object.keys(rawRows.value[0]).filter((k) => !k.startsWith("__") && !k.startsWith("列"));
});

const genericRows = computed(() =>
  rawRows.value.filter((row) => genericColumns.value.some((col) => !isBlank(row[col])))
);

let loadDataSeq = 0;

async function loadData() {
  if (!props.workbookId) return;
  const seq = ++loadDataSeq;
  loading.value = true;
  error.value = "";
  syncHint.value = "";
  try {
    if (isInspectionLayout.value || isOqcLayout.value) {
      await loadClassifications();
      if (isInspectionLayout.value || isOqcLayout.value) {
        await loadRawRows();
      }
      if (isOqcLayout.value && !oqcSectionHeads.value.length) {
        oqcSectionHeads.value = extractSectionHeadsFromRows(rawRows.value);
      }
      if (isOqcLayout.value && !oqcModelOwners.value.length) {
        oqcModelOwners.value = extractModelOwnersFromRows(rawRows.value);
      }
      if (isOqcLayout.value && !oqcModelSections.value.length) {
        oqcModelSections.value = extractModelSectionsFromRows(rawRows.value);
      }
    } else {
      classificationItems.value = [];
      moduleItems.value = [];
      await loadRawRows();
    }
  } catch (err) {
    error.value = String(err.message || err);
    rawRows.value = [];
    classificationItems.value = [];
    moduleItems.value = [];
  } finally {
    if (seq === loadDataSeq) loading.value = false;
  }
}

watch(
  () => [props.workbookId, props.sheetName],
  ([wid]) => {
    if (wid) loadData();
  },
  { immediate: true },
);

watch(oqcModelOwnerFilterOwnerOptions, (opts) => {
  const cur = oqcModelOwnerFilterOwner.value.trim();
  if (cur && !opts.includes(cur)) oqcModelOwnerFilterOwner.value = "";
});

watch(oqcModelOwnerFilterModelOptions, (opts) => {
  const cur = oqcModelOwnerFilterModel.value.trim();
  if (cur && !opts.includes(cur)) oqcModelOwnerFilterModel.value = "";
});
</script>

<style scoped>
.code-table-view {
  padding: 16px 18px 24px;
}

.view-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.view-head h2 {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--ink);
}

.hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.loading-hint,
.error-hint {
  padding: 24px;
  text-align: center;
  color: var(--muted);
}

.error-hint {
  color: var(--danger);
}

.top-row {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: 12px;
  align-items: start;
  margin-bottom: 12px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 12px;
}

.data-row {
  display: grid;
  grid-template-columns: max-content max-content minmax(420px, 1fr);
  align-items: start;
  gap: 24px;
  width: 100%;
}

.instructions {
  background: #fff8dc;
  border: 1px solid #e6c200;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.55;
}

.instructions-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.instructions ol {
  margin: 0;
  padding-left: 18px;
}

.instructions li + li {
  margin-top: 4px;
}

.lookup-panel {
  min-width: 0;
}

.lookup-panel--compact {
  width: max-content;
  max-width: 240px;
}

.main-panel {
  min-width: 0;
  width: 100%;
}

.code-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  background: #fff;
  border: 1px solid #c8c8c8;
}

.code-table th,
.code-table td {
  border: 1px solid #d9d9d9;
  padding: 4px 8px;
  text-align: left;
  vertical-align: top;
}

.code-table thead th {
  background: #ed7d31;
  color: #fff;
  font-weight: 600;
  text-align: center;
}

.code-table .subhead th {
  background: #f4b183;
  color: #fff;
  font-weight: 600;
}

.code-table tbody tr:nth-child(even) {
  background: #fafafa;
}

.code-table .num {
  text-align: center;
  width: 48px;
}

.code-table .code {
  font-weight: 600;
  white-space: nowrap;
}

.lookup-panel .code-table {
  width: max-content;
  min-width: 220px;
  table-layout: auto;
}

.main-panel .main-table {
  width: 100%;
  table-layout: auto;
}

.side-table th,
.side-table td {
  font-size: 11px;
  white-space: nowrap;
  padding: 5px 16px;
}

.side-table--compact th,
.side-table--compact td {
  padding: 4px 10px;
}

.status-table {
  width: auto;
}

.status-code {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.legend-swatch {
  width: 18px;
  height: 14px;
  border-radius: 2px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.legend-swatch.ok { background: #92d050; }
.legend-swatch.ok1 { background: #ffff00; }
.legend-swatch.ok2 { background: #ffc000; }
.legend-swatch.ng { background: #ff0000; }
.legend-swatch.ng-batch { background: #f4b084; }

.ghost-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 6px 12px;
  color: var(--primary);
}

.rule-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.rule-tabs button {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--muted);
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}

.rule-tabs button.on {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.inspection-layout {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) max-content;
  gap: 20px;
  align-items: start;
}

.inspection-layout--single {
  grid-template-columns: 1fr;
}

.oqc-model-row {
  grid-template-columns: repeat(auto-fit, minmax(220px, max-content));
}

.oqc-defects-panel {
  width: 100%;
}

.category-overview,
.oqc-overview {
  max-height: calc(100vh - 240px);
  overflow: auto;
  padding-right: 4px;
}

.oqc-sync-top {
  margin: 0 0 10px;
}

.oqc-section {
  margin-bottom: 22px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--line);
}

.oqc-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.oqc-owner-table-wrap {
  overflow: auto;
  max-height: min(70vh, 720px);
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
}

.oqc-owner-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.oqc-owner-table-head th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #c65a7a;
  color: #fff;
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid #b04a68;
}

.oqc-owner-table-filter th {
  position: sticky;
  top: 41px;
  z-index: 2;
  background: #f8f4f5;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
}

.table-filter-input,
.table-filter-select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  background: #fff;
  position: relative;
  z-index: 3;
}

.table-filter-clear {
  padding: 4px 10px;
  font-size: 12px;
}

.oqc-owner-table-row:nth-child(even) {
  background: #fafafa;
}

.oqc-owner-table-row:hover {
  background: #f3f8ff;
}

.oqc-owner-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  vertical-align: middle;
}

.oqc-owner-table .col-model {
  font-weight: 600;
  font-family: ui-monospace, Consolas, monospace;
  min-width: 120px;
}

.oqc-owner-table .col-owner {
  min-width: 140px;
}

.oqc-owner-table .col-actions {
  width: 88px;
  text-align: right;
  white-space: nowrap;
}

.empty-filter-hint {
  text-align: center;
  color: var(--muted);
  padding: 20px !important;
}

.oqc-section-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.bulk-rename-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}

.bulk-rename-count {
  margin: 0;
  font-size: 13px;
  color: var(--primary);
}

.oqc-section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.oqc-section-head h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 650;
  color: var(--ink);
}

.section-desc {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.45;
}

.section-desc strong {
  color: var(--ink);
  font-weight: 650;
}

.cls-index.defect-code {
  width: auto;
  min-width: 36px;
  font-weight: 650;
  font-size: 12px;
  color: var(--ink);
}

.oqc-meta-cards {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(280px, 1fr);
  gap: 12px;
  align-items: start;
}

.instructions-card {
  margin: 0;
}

.status-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.status-mini-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
}

.status-mini-card .status-code {
  font-size: 13px;
}

.status-desc {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.35;
}

.oqc-page-tabs {
  margin-bottom: 16px;
}

.pair-card-board {
  border: 1px solid #e8b4b8;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.pair-card-board--compact {
  max-width: 520px;
}

.pair-card-head,
.pair-card {
  display: grid;
  grid-template-columns: minmax(100px, 1fr) minmax(100px, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 8px 14px;
}

.pair-card-head {
  background: #f4cccc;
  font-size: 12px;
  font-weight: 650;
  color: #5c3d3d;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid #e8b4b8;
}

.pair-card {
  border-bottom: 1px solid #f0e0e0;
  font-size: 13px;
}

.pair-card:nth-child(even) {
  background: #fffafb;
}

.pair-card:last-child {
  border-bottom: none;
}

.pair-left {
  font-weight: 600;
}

.pair-right {
  color: var(--ink);
}

.pair-actions-placeholder {
  width: 52px;
}

.pair-card-actions {
  display: flex;
  gap: 2px;
  justify-content: flex-end;
}

.name-card-grid {
  display: grid;
  gap: 12px;
  align-items: stretch;
}

.name-card-grid--sections {
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  max-width: 960px;
}

.name-card-grid--models {
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
}

.name-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 16px 12px 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: linear-gradient(180deg, #fff 0%, #faf8ff 100%);
  box-shadow: 0 2px 8px rgba(91, 76, 143, 0.08);
  min-height: 118px;
}

.name-card--section {
  border-top: 3px solid #ed7d31;
}

.name-card--model {
  border-top: 3px solid var(--primary);
}

.name-card--model-section {
  border-top: 3px solid #70ad47;
  background: linear-gradient(180deg, #fff 0%, #f3faf0 100%);
}

.name-card-key {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.3;
  margin-bottom: 8px;
}

.name-card-value {
  font-size: 18px;
  font-weight: 650;
  color: #2d3748;
  line-height: 1.25;
  margin-bottom: 6px;
}

.name-card-foot {
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.name-card-actions {
  position: absolute;
  top: 6px;
  right: 4px;
  display: flex;
  gap: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.name-card:hover .name-card-actions {
  opacity: 1;
}

.name-card-grid--editable .name-card {
  padding-top: 22px;
}

.overview-summary {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--muted);
}

.overview-summary strong {
  color: var(--ink);
  font-weight: 650;
}

.overview-hint {
  color: var(--muted);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  align-items: start;
}

.category-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.oqc-overview .cls-actions {
  opacity: 1;
}

.category-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #fafafa;
  border-bottom: 1px solid var(--line);
}

.category-card-head h3 {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-add-btn {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--primary);
  cursor: pointer;
  flex-shrink: 0;
}

.card-add-btn:hover {
  border-color: var(--primary);
  background: var(--primary-light);
}

.classification-list.compact {
  padding: 6px 8px 8px;
  max-height: 320px;
  overflow-y: auto;
}

.classification-list.compact .classification-item {
  padding: 7px 10px;
  margin-bottom: 2px;
}

.category-search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0 14px;
}

.category-search-bar input {
  width: min(460px, 100%);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 12px;
  color: var(--ink);
  background: #fff;
  font-size: 14px;
}

.category-search-bar input:focus {
  outline: 2px solid color-mix(in srgb, var(--primary) 25%, transparent);
  border-color: var(--primary);
}

.search-result-hint { color: var(--muted); font-size: 13px; }

.category-empty-hint {
  margin: 0;
  padding: 16px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.category-browser {
  display: grid;
  grid-template-columns: minmax(200px, 240px) minmax(0, 1fr);
  gap: 16px;
  min-height: 420px;
  max-height: calc(100vh - 280px);
}

.category-nav {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fafafa;
  overflow: auto;
  padding: 8px;
}

.category-nav-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.nav-count {
  background: var(--primary-light);
  color: var(--primary);
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 11px;
}

.category-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 1px solid transparent;
  background: #fff;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: var(--ink);
}

.category-nav-item.on {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.cat-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.cat-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cat-count {
  font-size: 11px;
  color: var(--muted);
  background: #f3f4f6;
  border-radius: 999px;
  padding: 1px 7px;
}

.category-nav-item.on .cat-count {
  background: rgba(255, 255, 255, 0.7);
}

.classification-detail {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  background: #fafafa;
  position: sticky;
  top: 0;
  z-index: 1;
}

.detail-head h3 {
  margin: 0 0 4px;
  font-size: 16px;
}

.detail-head p {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}

.classification-list {
  list-style: none;
  margin: 0;
  padding: 8px;
}

.classification-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border-left: 3px solid #cbd5e1;
  margin-bottom: 4px;
}

.classification-item:hover {
  background: #f8fafc;
}

.cls-index {
  width: 28px;
  text-align: center;
  font-size: 11px;
  color: var(--muted);
  flex-shrink: 0;
}

.cls-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.4;
}

.cls-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.classification-item:hover .cls-actions {
  opacity: 1;
}

.module-grid-wrap {
  max-height: calc(100vh - 280px);
  overflow: auto;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.module-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 14px;
  background: #fff;
}

.module-card:hover {
  border-color: #ed7d31;
  box-shadow: 0 2px 8px rgba(237, 125, 49, 0.12);
}

.module-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}

.module-owner {
  font-size: 13px;
  color: var(--ink);
}

.owner-label {
  display: inline-block;
  font-size: 11px;
  color: var(--muted);
  margin-right: 6px;
}

.module-card-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.empty-hint {
  margin: 0;
  padding: 24px 16px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}

.cat-dot.cat-standard,
.classification-item.cat-standard { border-left-color: #e6b800; }
.cat-dot.cat-operation,
.classification-item.cat-operation { border-left-color: #70ad47; }
.cat-dot.cat-status,
.classification-item.cat-status { border-left-color: #a6a6a6; }
.cat-dot.cat-inspection,
.classification-item.cat-inspection { border-left-color: #5b9bd5; }
.cat-dot.cat-mix,
.classification-item.cat-mix { border-left-color: #4472c4; }
.cat-dot.cat-sampling,
.classification-item.cat-sampling { border-left-color: #ed7d31; }
.cat-dot.cat-first,
.classification-item.cat-first { border-left-color: #c65911; }
.cat-dot.cat-access,
.classification-item.cat-access { border-left-color: #ffc000; }
.cat-dot.cat-esd,
.classification-item.cat-esd { border-left-color: #92d050; }
.cat-dot.cat-sample,
.classification-item.cat-sample { border-left-color: #9dc3e6; }
.cat-dot.cat-instrument,
.classification-item.cat-instrument { border-left-color: #808080; }
.cat-dot.cat-glue,
.classification-item.cat-glue { border-left-color: #f4b084; }
.cat-dot.cat-5s,
.classification-item.cat-5s { border-left-color: #ffd966; }
.cat-dot.cat-default,
.classification-item.cat-default { border-left-color: #cbd5e1; }

.cat-dot.cat-standard { background: #fff2cc; }
.cat-dot.cat-operation { background: #e2efda; }
.cat-dot.cat-status { background: #ededed; }
.cat-dot.cat-inspection { background: #ddebf7; }
.cat-dot.cat-mix { background: #d9e1f2; }
.cat-dot.cat-sampling { background: #fce4d6; }
.cat-dot.cat-first { background: #f8cbad; }
.cat-dot.cat-access { background: #fff2cc; }
.cat-dot.cat-esd { background: #e2efda; }
.cat-dot.cat-sample { background: #ddebf7; }
.cat-dot.cat-instrument { background: #ededed; }
.cat-dot.cat-glue { background: #fce4d6; }
.cat-dot.cat-5s { background: #fff2cc; }
.cat-dot.cat-default { background: #e5e7eb; }

.cat-dot.cat-oqc-section,
.classification-item.cat-oqc-section { border-left-color: #70ad47; }
.cat-dot.cat-oqc-section { background: #e2efda; }

.cat-dot.cat-oqc-owner,
.classification-item.cat-oqc-owner { border-left-color: var(--primary, #5b4c8f); }
.cat-dot.cat-oqc-owner { background: var(--primary-light, #ede9f8); }

.category-grid--heads {
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  max-width: 960px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.sync-hint {
  font-size: 12px;
  color: var(--muted);
}

.tab-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
}

.primary-btn {
  border: none;
  background: var(--primary);
  color: #fff;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 13px;
}

.actions-col {
  width: 72px;
  text-align: center;
  white-space: nowrap;
}

.icon-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 4px;
  font-size: 14px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.modal-panel {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  width: min(420px, 100%);
}

.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.dialog-head h3 {
  margin: 0;
  font-size: 15px;
}

.editor-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.field input {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.field-hint {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.4;
}

.editor-error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}

@media (max-width: 900px) {
  .top-row {
    grid-template-columns: 1fr;
  }

  .data-row {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .lookup-panel .code-table {
    width: 100%;
    min-width: 0;
  }

  .category-browser {
    grid-template-columns: 1fr;
    max-height: none;
  }

  .category-nav {
    max-height: 220px;
  }

  .module-grid {
    grid-template-columns: 1fr;
  }

  .oqc-section-head {
    flex-direction: column;
    align-items: stretch;
  }

  .oqc-meta-cards {
    grid-template-columns: 1fr;
  }
}
</style>
