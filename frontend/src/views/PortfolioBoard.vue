<template>
  <div class="portfolio-board">
    <!-- 头部 -->
    <div class="board-header">
      <div class="header-title">
        <h2>我的持仓组合</h2>
        <p>管理您的投资组合</p>
      </div>
      <el-button type="primary" @click="showCreatePortfolioDialog">
        <el-icon><Plus /></el-icon>
        创建组合
      </el-button>
    </div>

    <!-- 看板内容 -->
    <div class="board-content">
      <!-- 组合卡片列表 -->
      <div class="portfolio-grid">
        <div
          v-for="portfolio in portfolios"
          :key="portfolio.id"
          class="portfolio-card">
          <!-- 卡片头部 -->
          <div class="card-header">
            <div class="card-title">
              <el-icon class="icon"><Folder /></el-icon>
              <span>{{ portfolio.name }}</span>
            </div>
            <div class="card-actions">
              <el-button size="small" @click.stop="editPortfolio(portfolio)">编辑</el-button>
              <el-button size="small" type="danger" @click.stop="deletePortfolio(portfolio)">删除</el-button>
            </div>
          </div>

          <!-- 卡片统计 -->
          <div class="card-stats">
            <div class="stat-item">
              <span class="stat-label">持仓数量</span>
              <span class="stat-value">{{ portfolio.positions?.length || portfolio.position_count || 0 }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">总市值</span>
              <span class="stat-value">¥{{ formatNumber(portfolio.total_value) }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">总成本</span>
              <span class="stat-value">¥{{ formatNumber(portfolio.total_cost) }}</span>
            </div>
            <div class="stat-item" :class="{ 'profit': portfolio.total_profit_loss >= 0, 'loss': portfolio.total_profit_loss < 0 }">
              <span class="stat-label">总盈亏</span>
              <span class="stat-value">{{ portfolio.total_profit_loss >= 0 ? '+' : '' }}¥{{ formatNumber(portfolio.total_profit_loss) }}</span>
            </div>
          </div>

          <!-- 持仓功能区 -->
          <div class="card-content">
            <!-- 持仓列表 -->
            <div class="positions-list">
              <div class="positions-header">
                <span>持仓基金</span>
                <el-button size="small" type="success" @click="showAddPositionDialog(portfolio)">
                  <el-icon><Plus /></el-icon>
                  添加持仓
                </el-button>
              </div>
              
              <div v-if="!portfolio.positions || portfolio.positions.length === 0" class="empty-state">
                <el-icon :size="48" style="color: #ccc;"><Box /></el-icon>
                <p>暂无持仓，点击上方按钮添加</p>
              </div>

              <div v-else class="position-items">
                <div
                  v-for="position in portfolio.positions"
                  :key="position.id"
                  class="position-item"
                >
                  <div class="position-info">
                    <div class="fund-name">
                      <span class="fund-code">{{ position.fund_code }}</span>
                      <span>{{ position.fund_name }}</span>
                    </div>
                    <div class="position-detail">
                      <span>份额: {{ position.shares }}份</span>
                      <span>成本: ¥{{ position.cost_price }}</span>
                    </div>
                  </div>
                  <div class="position-stats">
                    <div class="current-value">¥{{ formatNumber(position.current_value) }}</div>
                    <div :class="{ 'profit': position.profit_loss >= 0, 'loss': position.profit_loss < 0 }">
                      {{ position.profit_loss >= 0 ? '+' : '' }}¥{{ formatNumber(position.profit_loss) }}
                      ({{ position.profit_loss_rate >= 0 ? '+' : '' }}{{ position.profit_loss_rate }}%)
                    </div>
                  </div>
                  <div class="position-actions-wrapper">
                    <div class="position-actions">
                      <el-tooltip content="编辑" placement="top">
                        <el-button size="small" circle @click="editPosition(position)">
                          <el-icon><Edit /></el-icon>
                        </el-button>
                      </el-tooltip>
                      <el-tooltip content="从组合移除" placement="top">
                        <el-button size="small" circle type="danger" @click="deletePosition(position)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>


      </div>
    </div>

    <!-- 创建/编辑组合对话框 -->
    <el-dialog
      v-model="portfolioDialogVisible"
      :title="isEditPortfolio ? '编辑组合' : '创建组合'"
      width="500px">
      <el-form :model="portfolioForm" label-width="100px">
        <el-form-item label="组合名称" required>
          <el-input v-model="portfolioForm.name" placeholder="请输入组合名称" />
        </el-form-item>
        <el-form-item label="组合描述">
          <el-input v-model="portfolioForm.description" type="textarea" placeholder="请输入组合描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="portfolioDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPortfolio">确定</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑持仓对话框 -->
    <el-dialog
      v-model="positionDialogVisible"
      :title="isEditPosition ? '编辑持仓' : '添加持仓'"
      width="500px">
      <el-form :model="positionForm" label-width="100px">
        <el-form-item label="基金代码" required>
          <FundSelect v-model="positionForm.fund_code" placeholder="请选择基金" @select="onPositionFundSelect" />
        </el-form-item>
        <el-form-item label="基金名称">
          <el-input v-model="positionForm.fund_name" disabled />
        </el-form-item>
        <el-form-item label="持仓份额" required>
          <el-input v-model.number="positionForm.shares" placeholder="请输入持仓份额" />
        </el-form-item>
        <el-form-item label="成本价" required>
          <el-input v-model.number="positionForm.cost_price" placeholder="请输入成本价" />
        </el-form-item>
        <el-form-item label="当前净值">
          <el-input v-model.number="positionForm.current_price" placeholder="请输入当前净值" />
        </el-form-item>
        <el-form-item label="买入日期" required>
          <el-date-picker v-model="positionForm.buy_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="positionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPosition">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'PortfolioBoard' })
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Folder, Box, Edit, Delete } from '@element-plus/icons-vue';
import { portfolioApi } from '@/api';
import FundSelect from '@/components/FundSelect.vue';
// 数据
const portfolios = ref([]);
const loading = ref(false);
// 组合对话框
const portfolioDialogVisible = ref(false);
const isEditPortfolio = ref(false);
const editPortfolioId = ref(null);
const portfolioForm = ref({
 name: '',
 description: ''
});
// 持仓对话框
const positionDialogVisible = ref(false);
const isEditPosition = ref(false);
const editPositionId = ref(null);
const currentPortfolioId = ref(null);
// 已有持仓模式：添加持仓时若所选基金已有 position 记录，记下其 id，submit 时只创建关联而非新建持仓
const existingPositionId = ref(null);
const positionForm = ref({
 fund_code: '',
 fund_name: '',
 shares: 0,
 cost_price: 0,
 current_price: 0,
 buy_date: ''
});
// 获取组合列表
const fetchPortfolios = async () => {
 loading.value = true;
 try {
 const result = await portfolioApi.getPortfolios({ page: 1, page_size: 100 });
 portfolios.value = result.data;
 // 并行获取每个组合的持仓详情
 await Promise.all(portfolios.value.map(portfolio => fetchPortfolioPositions(portfolio)));
 }
 catch (error) {
 ElMessage.error('获取组合列表失败');
 }
 finally {
 loading.value = false;
 }
};

// 获取单个组合的持仓详情
const fetchPortfolioPositions = async (portfolio) => {
 try {
 const res = await portfolioApi.getPortfolioPositions(portfolio.id);
 portfolio.positions = res.data || [];
 portfolio.total_value = res.total_value || 0;
 portfolio.total_cost = res.total_cost || 0;
 portfolio.total_profit_loss = res.total_profit_loss || 0;
 }
 catch (error) {
 console.error(`获取组合 ${portfolio.name} 的持仓失败`);
 portfolio.positions = [];
 portfolio.total_value = 0;
 portfolio.total_cost = 0;
 portfolio.total_profit_loss = 0;
 }
};
// 显示创建组合对话框
const showCreatePortfolioDialog = () => {
 isEditPortfolio.value = false;
 editPortfolioId.value = null;
 portfolioForm.value = {
 name: '',
 description: ''
 };
 portfolioDialogVisible.value = true;
};
// 编辑组合
const editPortfolio = (portfolio) => {
 isEditPortfolio.value = true;
 editPortfolioId.value = portfolio.id;
 portfolioForm.value = {
 name: portfolio.name,
 description: portfolio.description
 };
 portfolioDialogVisible.value = true;
};
// 提交组合表单
const submitPortfolio = async () => {
 if (!portfolioForm.value.name) {
 ElMessage.warning('请输入组合名称');
 return;
 }
 try {
 if (isEditPortfolio.value) {
 await portfolioApi.updatePortfolio(editPortfolioId.value, portfolioForm.value);
 ElMessage.success('组合更新成功');
 }
 else {
 await portfolioApi.createPortfolio(portfolioForm.value);
 ElMessage.success('组合创建成功');
 }
 portfolioDialogVisible.value = false;
 fetchPortfolios();
 }
 catch (error) {
 ElMessage.error(isEditPortfolio.value ? '更新失败' : '创建失败');
 }
};
// 删除组合
const deletePortfolio = async (portfolio) => {
 try {
 await ElMessageBox.confirm('确定要删除这个组合吗？', '提示', { type: 'warning' });
 await portfolioApi.deletePortfolio(portfolio.id);
 ElMessage.success('删除成功');
 fetchPortfolios();
 }
 catch (error) {
 if (error !== 'cancel') {
 ElMessage.error('删除失败');
 }
 }
};
// 显示添加持仓对话框
const showAddPositionDialog = (portfolio) => {
 currentPortfolioId.value = portfolio.id;
 isEditPosition.value = false;
 editPositionId.value = null;
 existingPositionId.value = null;
 // 本地日期，避免 toISOString 在北京时间凌晨取到昨天
 const d = new Date();
 const todayLocal = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
 positionForm.value = {
 fund_code: '',
 fund_name: '',
 shares: 0,
 cost_price: 0,
 current_price: 0,
 buy_date: todayLocal
 };
 positionDialogVisible.value = true;
};
// 编辑持仓
const editPosition = (position) => {
 isEditPosition.value = true;
 editPositionId.value = position.id;
 currentPortfolioId.value = null; // 编辑时不需要组合ID
 positionForm.value = {
 fund_code: position.fund_code,
 fund_name: position.fund_name,
 shares: position.shares,
 cost_price: position.cost_price,
 current_price: position.current_price,
 buy_date: position.buy_date
 };
 positionDialogVisible.value = true;
};
// 提交持仓表单
const submitPosition = async () => {
 if (!positionForm.value.fund_code || !positionForm.value.shares || !positionForm.value.cost_price) {
 ElMessage.warning('请填写必填项');
 return;
 }
 try {
 if (isEditPosition.value) {
 await portfolioApi.updatePosition(editPositionId.value, positionForm.value);
 ElMessage.success('持仓更新成功');
 }
 else {
 // 已有持仓模式：所选基金已存在 position 记录，只创建组合-持仓关联，不新建持仓
 if (existingPositionId.value) {
 await portfolioApi.createPortfolioPosition({
 portfolio_id: currentPortfolioId.value,
 position_id: existingPositionId.value
 });
 ElMessage.success('已关联已有持仓');
 }
 else {
 // 新建持仓 + 关联
 const result = await portfolioApi.createPosition(positionForm.value);
 await portfolioApi.createPortfolioPosition({
 portfolio_id: currentPortfolioId.value,
 position_id: result.id
 });
 ElMessage.success('持仓添加成功');
 }
 }
 positionDialogVisible.value = false;
 fetchPortfolios();
 }
 catch (error) {
 ElMessage.error(isEditPosition.value ? '更新失败' : '添加失败');
 }
};
// 移除持仓：只删除组合-持仓关联，不删除持仓本身（持仓可被多组合共享/保留历史）
const deletePosition = async (position) => {
 if (!position.relation_id) {
 ElMessage.error('缺少关联信息，无法移除');
 return;
 }
 try {
 await ElMessageBox.confirm(`确定从本组合移除 ${position.fund_name} 吗？（持仓本身不删除）`, '提示', { type: 'warning' });
 await portfolioApi.deletePortfolioPosition(position.relation_id);
 ElMessage.success('已从组合移除');
 fetchPortfolios();
 }
 catch (error) {
 if (error !== 'cancel') {
 ElMessage.error('移除失败');
 }
 }
};
// 格式化数字
const formatNumber = (num) => {
 if (!num)
 return '0.00';
 return Number(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};
// 选择基金时联动：添加持仓若该基金已有持仓记录，带出已有数据（只建关联，不新建持仓）
const onPositionFundSelect = async (fund) => {
 if (!fund) {
 positionForm.value.fund_name = '';
 existingPositionId.value = null;
 return;
 }
 positionForm.value.fund_name = fund.fund_name;
 // 编辑模式不查已有持仓
 if (isEditPosition.value) {
 existingPositionId.value = null;
 return;
 }
 // 添加模式：查该基金是否已有持仓，有则带出
 try {
 const res = await portfolioApi.getPositionByFund(fund.fund_code);
 const existing = res.data;
 if (existing) {
 existingPositionId.value = existing.id;
 positionForm.value.shares = existing.shares;
 positionForm.value.cost_price = existing.cost_price;
 positionForm.value.current_price = existing.current_price;
 positionForm.value.buy_date = existing.buy_date || positionForm.value.buy_date;
 ElMessage.info(`该基金已有持仓，将直接关联到本组合（不新建持仓）`);
 }
 else {
 existingPositionId.value = null;
 positionForm.value.current_price = fund.net_asset_value || 0;
 }
 } catch (e) {
 existingPositionId.value = null;
 }
};
onMounted(() => {
 fetchPortfolios();
});
</script>

<style scoped>
.portfolio-board {
  padding: 24px;
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 20px 24px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.header-title h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #1f2937;
  letter-spacing: 0.5px;
}

.header-title p {
  margin: 6px 0 0 0;
  font-size: 14px;
  color: #6b7280;
}

.board-content {
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(15px); }
  to { opacity: 1; transform: translateY(0); }
}

.portfolio-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
  gap: 24px;
}

.portfolio-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  border: 1px solid #f0f2f5;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.card-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 600;
  font-size: 18px;
  color: white;
}

.icon {
  color: rgba(255, 255, 255, 0.9);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-actions .el-button {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
}

.card-actions .el-button:hover {
  background: rgba(255, 255, 255, 0.3);
}

.card-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 20px 24px;
  gap: 16px;
  background: #fafbfc;
}

.stat-item {
  text-align: center;
  padding: 12px 8px;
  background: white;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
  font-weight: 500;
}

.stat-value {
  display: block;
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.stat-item.profit .stat-value {
  color: #ef4444;
}

.stat-item.loss .stat-value {
  color: #10b981;
}

.card-content {
  padding: 20px 24px;
}

.positions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.positions-header span {
  font-weight: 600;
  font-size: 16px;
  color: #374151;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #9ca3af;
}

.empty-state p {
  margin: 12px 0 0 0;
  font-size: 14px;
}

.position-items {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.position-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 10px;
  background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
  border-radius: 12px;
  transition: all 0.25s ease;
  border: 1px solid #e5e7eb;
}

.position-item:hover {
  background: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  border-color: #d1d5db;
}

.position-info {
  flex: 1;
  min-width: 0;
  margin-right: 16px;
}

.fund-name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 8px;
  font-size: 15px;
}

.fund-code {
  font-size: 12px;
  font-weight: 600;
  color: #667eea;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
  padding: 3px 8px;
  border-radius: 6px;
}

.position-detail {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: #6b7280;
}

.position-detail span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.position-stats {
  min-width: 140px;
  margin-right: 0;
}

.current-value {
  font-weight: 700;
  color: #1f2937;
  font-size: 16px;
  margin-bottom: 4px;
}

.position-stats .profit {
  color: #ef4444;
  font-weight: 600;
  font-size: 14px;
}

.position-stats .loss {
  color: #10b981;
  font-weight: 600;
  font-size: 14px;
}

.position-actions-wrapper {
  width: 36px;
  flex-shrink: 0;
}

.position-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.position-item:hover .position-actions {
  opacity: 1;
}

.position-actions .el-button {
  width: 28px;
  height: 28px;
  padding: 0;
  margin-left: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>